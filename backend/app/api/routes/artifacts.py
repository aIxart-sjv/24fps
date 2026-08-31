"""
API routes for reading derived-artifact metadata and downloading/streaming
artifact bytes (Master Specification Section 20, "Media Artifact Model").

Phase 23 gap assessment (frontend/backend integration audit): no route
anywhere served an artifact's actual file content. The report download
route (`GET /reports/{report_id}/download`, Phase 18) is the closest
precedent and this route follows the same shape, but reads from
`Artifact.path` (already a backend-resolved, root-bound path -- never a
client-supplied one) instead of a report's path. Required for the
frontend video workspace to actually play back a derived recording
(Phase 9's H.264 preview / H.265 master) rather than assuming the
original proprietary evidence file is browser-playable (task Phase 23
scope, "Recording / Video Workspace": "Do not assume a CPV file is
browser playable... use the derived media artifact").

Never serves anything outside `Artifact.path` -- the artifact ID is the
only client input, and it is resolved through the existing `Artifact`
table, never through a caller-supplied filesystem path (task Phase 23
scope, "File Downloads": "Do not expose arbitrary server filesystem
paths to the browser").
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    require_case_access_for_artifact,
    require_case_access_for_artifact_download,
    require_case_access_for_evidence,
)
from app.models import Artifact, Evidence
from app.schemas.artifact import ArtifactResponse
from app.storage.db import get_db

router = APIRouter()


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(
    artifact: Artifact = Depends(require_case_access_for_artifact),
) -> ArtifactResponse:
    """Retrieve one derived artifact's metadata (never its bytes)."""
    return ArtifactResponse.model_validate(artifact)


@router.get("/evidence/{evidence_id}/artifacts", response_model=list[ArtifactResponse])
def list_evidence_artifacts(
    evidence_id: int,
    db: Session = Depends(get_db),
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> list[ArtifactResponse]:
    """List every derived artifact produced from one evidence item, oldest
    first -- the full source/derived provenance chain (Phase 24 task
    scope, "Evidence Details": "Make source vs derived relationships
    obvious"). `parent_artifact_id` on each row lets the frontend render
    the chain (e.g. source recording -> H.265 master -> H.264 preview)
    without a second, separate endpoint."""
    del evidence
    artifacts = (
        db.query(Artifact).filter(Artifact.evidence_id == evidence_id).order_by(Artifact.id).all()
    )
    return [ArtifactResponse.model_validate(a) for a in artifacts]


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact: Artifact = Depends(require_case_access_for_artifact_download),
) -> FileResponse:
    """Stream one derived artifact's file content (e.g. a recovered
    recording, an H.264 preview, an acquisition manifest).

    Streamed directly from disk (`FileResponse`), not read fully into
    memory first -- derived video artifacts can be large.
    """
    artifact_id = artifact.id
    path = Path(artifact.path)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"artifact {artifact_id}'s file is missing on disk",
        )
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path=path, media_type=media_type, filename=path.name)
