"""
SQLAlchemy ORM model for processing/provenance history (Phase 15).
Master Specification Section 39 ("Provenance Engine"), Section 40
("Chain of Custody"), Section 50 (`provenance_events`/`custody_events`
tables), Section 51 rule 5 ("Audit/custody events must be append-oriented").

One table, `ProcessingEvent`, not two: Section 50 lists `provenance_events`
(id, case_id, evidence_id, artifact_id, event_type, actor, timestamp,
details, software_version, component_version, previous_hash, current_hash)
and `custody_events` (id, case_id, evidence_id, event_type, actor,
timestamp, details, previous_event_hash, current_event_hash) as two
nearly-identical terse tables. The Phase 15 task's own section 3 explicitly
asks for "one coherent typed processing-event concept... do not create a
separate table for every pipeline phase" -- this model merges both terse
tables into that one concept, plus the task's own richer field list
(input/output artifact references, tool/version, parameters, started_at/
completed_at, status, warnings). This is the same terse-table-vs-richer-
task-scope resolution pattern used repeatedly since Phase 10.

Append-only by construction: `app.core.provenance_manager.
ProvenanceManager` only ever INSERTs a fully-populated row via
`record_event` -- no method anywhere updates a `ProcessingEvent` after
creation, satisfying Section 51 rule 5 without relying on convention
alone. This is why the table is not simply an extension of `Job` (Phase
13): `Job` rows are deliberately mutated in place as work progresses
(`mark_running`, `finish_job`), which would violate append-only if reused
here.

`previous_hash`/`current_hash` are the exact columns Section 50 documents
on both source tables -- kept here, always `NULL` in this phase. Phase 16
(`app.audit.hash_chain`, still an empty stub) is the phase that computes
and populates them, mirroring how `RecoveryResult.timestamp_error`
existed as a documented column from Phase 10 onward but stayed `NULL`
until Phase 11 populated it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.evidence import Evidence
    from app.models.job import Job

__all__ = ["ProcessingEvent"]


class ProcessingEvent(Base):
    """One finished-fact record of a processing/custody operation.

    `operation` is a plain string validated at the call site against
    `app.audit.events.ProcessingOperation` (pipeline-stage events) or
    `app.audit.chain_of_custody.CustodyEventType` (evidence-lifecycle
    milestones) -- either vocabulary may populate this column, matching
    the established `GroundTruth.event_type`/`ValidationMetric.
    validation_type` (Phase 14) convention of an unconstrained-at-the-DB
    string validated in Python.

    `input_artifact_ids`/`output_artifact_ids`/`parameters`/`warnings`
    are JSON-encoded text columns, matching the established
    `RecordingMetadata`/`Job` JSON-in-text convention (Phase 9/13) --
    variable-shape data that does not need a normalized child table.
    """

    __tablename__ = "processing_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=True, index=True
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(256), nullable=False)
    #: `"human"` or `"system"` (`app.audit.events.ActorType`). Always
    #: supplied explicitly by the caller -- never inferred from `actor`.
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    tool: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_artifact_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_artifact_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    #: Always `NULL` in Phase 15 -- Phase 16 territory (Master
    #: Specification Section 41). Never computed or populated here.
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    case: Mapped[Case] = relationship("Case", back_populates="processing_events")
    evidence: Mapped[Evidence | None] = relationship("Evidence")
    job: Mapped[Job | None] = relationship("Job")

    def __repr__(self) -> str:
        return f"<ProcessingEvent operation={self.operation!r} status={self.status!r}>"
