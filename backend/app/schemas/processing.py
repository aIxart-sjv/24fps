"""
Pydantic schemas for the automatic case-processing API (Phase 22).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.job import JobResponse


class ProcessingPolicyRequest(BaseModel):
    """Optional overrides for `app.core.processing_policy.ProcessingPolicy`.
    Every field defaults to that dataclass's own documented default when
    omitted -- see its module docstring for the automation-tier rationale
    behind each default."""

    run_extraction: bool = True
    run_recovery: bool = True
    run_timestamp_normalization: bool = True
    run_ai: bool = False
    ai_analysis_types: list[str] | None = None
    run_correlation: bool = True
    run_validation: bool = True
    force_reprocess: bool = False
    notify: bool = True


class ProcessingRunRequest(BaseModel):
    """Request body for `POST /cases/{case_id}/process`. All fields optional
    -- an empty body runs the default policy."""

    policy: ProcessingPolicyRequest | None = None


class ProcessingStageResponse(BaseModel):
    """One dependency-tracked pipeline-stage job within a processing run."""

    id: int
    job_type: str
    status: str
    evidence_id: int | None
    recording_ids: list[int] | None
    progress: float | None
    results_count: int
    error: str | None
    warnings: list[str] | None
    started_at: str | None
    completed_at: str | None


class ProcessingRunResponse(BaseModel):
    """The root orchestration run plus its dependency-tracked children and
    observability counters (task Phase 22 scope, "Observability")."""

    root_job: JobResponse
    stages: list[ProcessingStageResponse]
    stages_total: int
    stages_completed: int
    stages_failed: int
    stages_skipped: int
    stages_blocked: int
    stages_requires_review: int
    new_finding_ids: list[int] = Field(default_factory=list)
    notification_ids: list[int] = Field(default_factory=list)
