"""
API route for reading recovery results (Phase 10, "Recovery Engine").
Master Specification Section 46 (API Design), `RECOVERY` section.

Only `GET /evidence/{evidence_id}/recovery-results` is added here. The
spec's other two recovery routes
(`POST /evidence/{id}/recovery/jobs`, `GET /recovery/jobs/{job_id}`) are
job-based, and no job system exists anywhere in this codebase yet
(`app/core/job_manager.py`, `app/storage/job_store.py`,
`app/api/routes/jobs.py` are all still empty stubs) — building one is out
of this phase's scope. Triggering a recovery attempt is a plain Python
call, `app.core.recovery_manager.RecoveryManager.run_recovery`, exactly
matching how `app.core.recording_manager.RecordingManager` already works
underneath its own routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.recovery_manager import RecoveryManager
from app.schemas.recovery import RecoveryResultResponse
from app.storage.db import get_db

router = APIRouter()


@router.get("/evidence/{evidence_id}/recovery-results", response_model=list[RecoveryResultResponse])
def list_recovery_results(
    evidence_id: int, db: Session = Depends(get_db)
) -> list[RecoveryResultResponse]:
    """List every recovery attempt recorded against one evidence item, newest first."""
    results = RecoveryManager.list_recovery_results(db, evidence_id)
    return [RecoveryResultResponse.model_validate(r) for r in results]
