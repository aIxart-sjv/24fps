"""
API route for the generic processing-job system (Phase 13).
Master Specification Section 46 (API Design), `JOBS` section:
`GET /api/v1/jobs/{job_id}`.

Generic on purpose: this route works for any `Job.job_type`, not just
`"ai"` -- reused as-is by `POST /api/v1/ai/jobs`' job status lookup, and
available to any future job type (validation, reporting, ...) without a
new route. `GET /api/v1/jobs/{job_id}/logs` is not implemented: no
structured processing-event-log subsystem exists yet (Master
Specification Section 49 is a separate, later concern).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.job_manager import JobManager
from app.models import Job
from app.schemas.job import JobResponse
from app.storage.db import get_db

router = APIRouter()


def _job_response(job: Job) -> JobResponse:
    """Decode a `Job`'s JSON-encoded text columns into plain Python values."""
    return JobResponse(
        id=job.id,
        case_id=job.case_id,
        evidence_id=job.evidence_id,
        parent_job_id=job.parent_job_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        worker=job.worker,
        recording_ids=json.loads(job.recording_ids) if job.recording_ids else None,
        analysis_types=json.loads(job.analysis_types) if job.analysis_types else None,
        model_versions=json.loads(job.model_versions) if job.model_versions else None,
        parameters=json.loads(job.parameters) if job.parameters else None,
        software_version=job.software_version,
        results_count=job.results_count,
        input_artifacts=json.loads(job.input_artifacts) if job.input_artifacts else None,
        output_artifacts=json.loads(job.output_artifacts) if job.output_artifacts else None,
        error=job.error,
        warnings=json.loads(job.warnings) if job.warnings else None,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobResponse:
    """Retrieve one processing job by ID, regardless of its `job_type`."""
    job = JobManager.get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job with id {job_id} not found"
        )
    return _job_response(job)
