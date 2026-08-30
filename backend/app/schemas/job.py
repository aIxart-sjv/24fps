"""
Pydantic schemas for the generic processing-job system (Phase 13).
Master Specification Section 46 (API Design), `JOBS` section:
`GET /api/v1/jobs/{job_id}`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobResponse(BaseModel):
    """One processing job, with its JSON-encoded columns decoded to
    plain Python values (never returned as opaque strings)."""

    id: int
    case_id: int
    evidence_id: int | None
    parent_job_id: int | None
    job_type: str
    status: str
    progress: float | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    worker: str | None
    recording_ids: list[int] | None
    analysis_types: list[str] | None
    model_versions: dict[str, str] | None
    parameters: dict[str, object] | None
    software_version: str | None
    results_count: int
    input_artifacts: list[int] | None
    output_artifacts: list[int] | None
    error: str | None
    warnings: list[str] | None
