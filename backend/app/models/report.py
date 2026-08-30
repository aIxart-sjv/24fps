"""
SQLAlchemy ORM model for standardized report artifacts (Phase 18).
Master Specification Section 43 ("Reporting Engine"), Section 50's
`reports` table (`id`, `case_id`, `report_type`, `path`, `created_at`,
`software_version`, `report_hash`, `status`).

`report_type` (the doc's literal column name) stores the *format* of this
row's single output file (`"json"` or `"pdf"`) -- Phase 18 implements one
report *content* (the standardized forensic report), rendered in two
formats, so "type" and "format" collapse to the same value here; this
resolution is documented rather than silently adding a redundant column.

One row always represents exactly one generated file (one `path`, one
`report_hash`) -- matching the doc's table shape directly, rather than
inventing a "one row, two files" schema it does not describe. Generating
"a report" (task Phase 18 scope: both JSON and PDF) therefore creates two
rows sharing one `job_id` and one assembled snapshot of case state (see
`app.core.report_manager.ReportManager.generate_report`), so their
content is guaranteed consistent with each other even though they are
two separate database rows.

Fields beyond the doc's literal eight, each required by a specific task
Phase 18 scope instruction rather than speculative:
- `job_id`: links this row back to the `Job` that produced it (task
  Phase 18 scope section 23: "If the existing job system is
  appropriate, reuse it" -- every other phase's persisted result already
  carries this same FK, e.g. `AIResult.job_id`/`ValidationMetric.job_id`).
- `report_schema_version`: task Phase 18 scope section 4 explicitly
  requires keeping the report *schema* version distinct from
  `software_version` (the running backend build) -- the doc's table only
  has the latter.
- `completed_at`: when generation of *this* file finished, distinct from
  `created_at` (this row's own creation time) -- mirrors the
  `Job.started_at`/`completed_at` pattern already used throughout.
- `error`/`warnings`: task Phase 18 scope section 5's "error information"
  and the general "warnings" field present on nearly every other
  persisted result in this codebase (`RecoveryResult.notes`,
  `ProcessingEvent.warnings`/`error`, ...). A `Report` row is only ever
  created after successful generation (task Phase 18 scope section 24:
  "Do not report success if required report generation failed" --
  failures are recorded on the `Job` row instead, never as a fabricated
  `Report` row), so `error` stays `NULL` in practice; `warnings` carries
  forward any limitations the assembled report content itself surfaced.

Never stores the complete report body in the database (task Phase 18
scope section 26: "Do not redundantly store the complete report body") --
only the file path and its hash. The file itself lives under
`REPORT_ROOT` (`app.storage.artifact_store.resolve_report_path`), never
inside the preserved evidence root.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.job import Job

__all__ = ["Report", "ReportStatus"]


class ReportStatus(str, Enum):
    """Outcome of generating one report file. Only `COMPLETED` rows are
    ever persisted in normal operation (see module docstring); `FAILED`
    exists for schema completeness/future-proofing and is never written
    by `app.core.report_manager.ReportManager` today."""

    COMPLETED = "completed"
    FAILED = "failed"


class Report(Base):
    """One generated standardized report file (JSON or PDF) for a case."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    report_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    software_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case: Mapped[Case] = relationship("Case", back_populates="reports")
    job: Mapped[Job | None] = relationship("Job")

    def __repr__(self) -> str:
        return f"<Report case_id={self.case_id} report_type={self.report_type!r} status={self.status!r}>"
