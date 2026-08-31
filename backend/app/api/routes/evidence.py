"""
API route for uploading a new evidence file and registering it in one
call (Master Specification Section 46 (API Design), `EVIDENCE` section).

Phase 23 gap assessment: `POST /cases/{case_id}/evidence`
(`app/api/routes/cases.py`) already registers evidence, but only against
a `source_path` the caller asserts is *already reachable on the server's
filesystem* -- there was no way for a browser-based officer to actually
get an evidence file onto the server at all. This route is that missing
piece: it accepts a real multipart file upload, writes it into the
configured `EVIDENCE_ROOT` using the same root-bound path-safety helper
`app.storage.artifact_store` already uses for derived artifacts
(`resolve_path_within_root` -- never a client-supplied absolute path,
never a path outside `EVIDENCE_ROOT`), then registers it through the
existing, unmodified `EvidenceManager.register_evidence`. No second
evidence-registration path is created; this only adds the upload step in
front of the one that already exists.

Streamed to disk in chunks (never fully buffered in memory) -- evidence
files (recordings, forensic images) can be large.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_case_access
from app.config import get_settings
from app.core.evidence_manager import EvidenceManager
from app.models import Case
from app.schemas.evidence import EvidenceCreateRequest, EvidenceResponse
from app.storage.db import get_db
from app.utils.paths import resolve_path_within_root

router = APIRouter()

_UPLOAD_CHUNK_SIZE = 1024 * 1024


def _safe_filename(name: str | None) -> str:
    """Reduce a client-supplied filename to a bare basename -- never a
    directory component, never empty."""
    candidate = Path(name or "").name.strip()
    return candidate or "evidence.bin"


@router.post(
    "/cases/{case_id}/evidence/upload",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence(
    case_id: int,
    evidence_id: str = Form(..., min_length=1, max_length=64),
    source_type: str = Form(..., min_length=1, max_length=64),
    source_description: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> EvidenceResponse:
    """Upload an evidence file and register it against `case_id` in one call."""
    settings = get_settings()
    relative_path = f"{case.case_id}/{evidence_id}_{_safe_filename(file.filename)}"
    try:
        destination = resolve_path_within_root(relative_path, settings.evidence_root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("wb") as out:
            while chunk := await file.read(_UPLOAD_CHUNK_SIZE):
                out.write(chunk)
    finally:
        await file.close()

    try:
        evidence = EvidenceManager.register_evidence(
            db,
            case_id,
            EvidenceCreateRequest(
                evidence_id=evidence_id,
                source_type=source_type,
                source_path=str(destination),
                source_description=source_description,
            ),
        )
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return EvidenceResponse.model_validate(evidence)
