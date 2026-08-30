"""
SQLAlchemy ORM model for the generic processing-job system.
Master Specification Section 48 ("Job System") and Section 35 ("AI
Processing Jobs").

No job system existed anywhere in this codebase before Phase 13
(`app/api/routes/recovery.py`'s own docstring: "no job system exists
anywhere in this codebase yet ... building one is out of this phase's
scope"). This is that system, built generically rather than as an
AI-only table, so future phases (validation, reporting, blockchain
anchoring -- all already named as `job_type` values in Section 48) can
reuse it without a new migration.

Section 48's generic job model (job_id, case_id, evidence_id, job_type,
status, progress, created_at, started_at, completed_at, worker,
input_artifacts, output_artifacts, error, warnings) and Section 35's
AI-specific elaboration of what an AI job additionally needs
(recording_ids, analysis_types, model_versions, results_count) describe
the same concept at two levels of detail -- the same kind of terse-list-
vs-richer-model gap Phase 10/12 already resolved by adding the extra
fields directly (Section 51 rule 8's `evidence_id` on `recovery_results`;
Phase 12's `ai_reference`/`recovery_status` on `timeline_events`). This
model does the same: Section 48's columns, plus the AI-specific ones,
plus a generic `parameters` column every future job type can also use for
its own reproducibility metadata.

`job_type` is a plain string (only `"ai"` is ever written by this phase)
rather than a constrained enum of job types this phase does not
implement -- Database Rule 11: "Unknown values must be explicit, not
fabricated."
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.evidence import Evidence


class JobStatus(str, Enum):
    """Explicit job-processing states (task Phase 13 scope's own
    vocabulary). `PARTIAL` exists specifically so a job that processed
    some but not all requested work is never misreported as `COMPLETED`.

    `SKIPPED`/`BLOCKED`/`REQUIRES_REVIEW` are Phase 22 additions (Master
    Specification Section 22 task scope, "Job Dependency Model": jobs must
    be able to expose these states honestly) -- `PENDING` already covers
    "queued" for the AI/report job types Phase 13/18 introduced, so no
    separate `QUEUED` value was added. `SKIPPED` means a step was not
    applicable given upstream results (e.g. no camera to correlate);
    `BLOCKED` means a step could not run because a dependency it needs
    did not itself complete successfully; `REQUIRES_REVIEW` means the
    step is examiner-controlled and was deliberately not run
    automatically (e.g. no ground-truth dataset configured).
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    REQUIRES_REVIEW = "requires_review"


#: `job_type` value this phase writes. A plain string column (not a DB
#: enum) so a future phase can introduce its own job types without a
#: migration -- Section 48 already names several ("validation", "report",
#: "blockchain_anchor", ...) this phase does not implement.
AI_JOB_TYPE = "ai"

#: `job_type` value Phase 18 (`app.core.report_manager.ReportManager`)
#: writes -- Master Specification Section 48's documented job-type
#: vocabulary lists "report". This module's own docstring already
#: anticipated a future reporting phase reusing this generic job layer.
REPORT_JOB_TYPE = "report"

#: `job_type` value Phase 22's `app.core.processing_orchestrator.
#: ProcessingOrchestrator` writes for the root, case-scoped orchestration
#: run. Individual pipeline stages it drives (identification, enumeration,
#: extraction, recovery, timestamp_normalization, timeline, correlation,
#: validation) are plain, self-describing `job_type` strings defined in
#: that module -- not enumerated here, matching this column's own
#: documented "unknown values must be explicit, not fabricated" design
#: (this module's docstring) rather than a second closed vocabulary.
ORCHESTRATION_JOB_TYPE = "orchestration"


class Job(Base):
    """One processing job (Master Specification Section 48).

    `recording_ids`/`analysis_types`/`model_versions`/`parameters`/
    `input_artifacts`/`output_artifacts`/`warnings` are JSON-encoded text
    columns, matching the established `RecordingMetadata`/Phase 9/12
    convention of JSON-encoding structured, variable-shape values into a
    free-text field rather than adding a normalized child table for pure
    job-configuration/audit metadata that nothing else queries
    relationally.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=True, index=True
    )
    #: Phase 22 addition: links a pipeline-stage job to the root
    #: orchestration `Job` that scheduled it, forming the dependency tree
    #: `ProcessingOrchestrator` builds (Master Specification Section 22
    #: task scope, "Job Dependency Model"). `NULL` for every job type
    #: Phases 13/18 already write (`"ai"`, `"report"`) when created
    #: directly through their own routes rather than via the
    #: orchestrator -- this column is purely additive and never required.
    parent_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=JobStatus.PENDING.value)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: The inference/processing device actually used (e.g. `"cpu"`,
    #: `"cuda:0"`) -- task Phase 13 scope: "Report which device was
    #: actually used for the job."
    worker: Mapped[str | None] = mapped_column(String(64), nullable=True)

    recording_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_versions: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    input_artifacts: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_artifacts: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[Case] = relationship("Case", back_populates="jobs")
    evidence: Mapped[Evidence | None] = relationship("Evidence")
    parent_job: Mapped[Job | None] = relationship("Job", remote_side=[id], back_populates="child_jobs")
    child_jobs: Mapped[list[Job]] = relationship("Job", back_populates="parent_job")

    def __repr__(self) -> str:
        return f"<Job id={self.id!r} job_type={self.job_type!r} status={self.status!r}>"
