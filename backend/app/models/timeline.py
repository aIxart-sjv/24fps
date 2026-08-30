"""
SQLAlchemy ORM model for canonical timeline events.
Master Specification Section 28 ("Canonical Timeline") — the `TimelineEvent`
shape: `event_id, case_id, camera_id, source_recording_id, event_type,
original_timestamp, normalized_timestamp, confidence, source, ai_reference,
recovery_status`. Section 50 (Database Model)'s `timeline_events` table
lists fewer columns (`description` present, `ai_reference`/
`recovery_status` absent) than Section 28's fuller conceptual model —
resolved the same way Phase 10 resolved the identical gap for
`recovery_results` (adding `evidence_id` there per Section 51 rule 8):
this model uses Section 50's column names and adds `ai_reference`/
`recovery_status`, both directly named by Section 28 and required by the
Phase 12 task's own event field list.

`correlation_id` (self-referential, nullable) is the one addition beyond
either section's list — it links a source event to the single
`event_type="correlated_event"` row that groups it, directly mirroring the
already-established `Artifact.parent_artifact_id` self-referential
pattern (Phase 4) rather than introducing a new "correlations" table.
Master Specification Section 28 already names `correlated_event` as one of
`timeline_events`'s own `event_type` values — a correlation result *is* a
`TimelineEvent` row, not a second concept.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.recording import Recording


class TimelineEvent(Base):
    """One event on the canonical, case-wide investigation timeline.

    `original_timestamp`/`normalized_timestamp` are read from wherever the
    event was ingested from (e.g. a `Recording`'s already-normalized
    fields) — this model never computes or corrects them; Phase 11 owns
    that (`app.core.timestamp_manager.TimestampManager`).
    """

    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recording_id: Mapped[int | None] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    normalized_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recovery_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[int | None] = mapped_column(
        ForeignKey("timeline_events.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    case: Mapped[Case] = relationship("Case", back_populates="timeline_events")
    recording: Mapped[Recording | None] = relationship("Recording")
    correlation: Mapped[TimelineEvent | None] = relationship(
        "TimelineEvent", remote_side=[id], back_populates="source_events"
    )
    source_events: Mapped[list[TimelineEvent]] = relationship(
        "TimelineEvent", back_populates="correlation"
    )

    def __repr__(self) -> str:
        return f"<TimelineEvent event_type={self.event_type!r} case_id={self.case_id!r}>"
