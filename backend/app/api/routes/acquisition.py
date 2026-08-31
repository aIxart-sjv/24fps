"""
API routes for evidence acquisition metadata (Phase 4/5, Master
Specification Section 12: "preserve acquisition metadata separately").

Phase 23 gap assessment: `app.core.evidence_manager.EvidenceManager.
record_acquisition_metadata` existed with no HTTP route at all -- the
frontend "Acquisition" view had nothing real to call, which is why the
supplied mock frontend simulated an entirely fictional "SATA-bridge
hardware read" sequence with a `setTimeout` progress bar (task Phase 23
scope: "Do not fake progress"; "Do NOT replace missing backend
functionality with fake frontend data"). This route is the real,
already-implemented capability that fiction stood in for: it opens the
evidence's already-registered source through the existing Phase 5
`EvidenceStorageReader` abstraction (never a live hardware device) and
records what that reader can actually determine (size, format, sector
size, any embedded provenance hash values) as a JSON manifest artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_case_access_for_evidence
from app.core.evidence_manager import EvidenceManager
from app.models import Artifact, Evidence
from app.schemas.artifact import ArtifactResponse
from app.storage.db import get_db

router = APIRouter()

_ACQUISITION_MANIFEST_ARTIFACT_TYPE = "acquisition_manifest"


@router.post(
    "/evidence/{evidence_id}/acquisition-manifest",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
def capture_acquisition_manifest(
    evidence_id: int,
    db: Session = Depends(get_db),
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> ArtifactResponse:
    """Capture and persist real acquisition-time metadata for a registered evidence item."""
    del evidence
    try:
        artifact = EvidenceManager.record_acquisition_metadata(db, evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ArtifactResponse.model_validate(artifact)


@router.get("/evidence/{evidence_id}/acquisition-manifest")
def get_acquisition_manifest(
    evidence_id: int,
    db: Session = Depends(get_db),
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> dict[str, Any]:
    """Return the most recently captured acquisition manifest's content, parsed as JSON.

    404 (not yet captured) is a normal, expected state -- distinct from
    "evidence not found" -- the caller is expected to `POST` first.
    """
    del evidence
    artifact = (
        db.query(Artifact)
        .filter(
            Artifact.evidence_id == evidence_id,
            Artifact.artifact_type == _ACQUISITION_MANIFEST_ARTIFACT_TYPE,
        )
        .order_by(Artifact.id.desc())
        .first()
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no acquisition manifest has been captured for evidence {evidence_id} yet",
        )
    path = Path(artifact.path)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"acquisition manifest artifact {artifact.id}'s file is missing on disk",
        )
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
