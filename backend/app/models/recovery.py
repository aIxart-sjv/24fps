"""
SQLAlchemy ORM model for recovery results.
Master Specification Section 50 (`TABLE: recovery_results`), Section 51
rule 8 ("Recovery results must reference the source evidence and
recording") — the source-list in Section 50 only names `recording_id`, so
`evidence_id` is added here as a second required foreign key to satisfy
rule 8 explicitly. `artifact_id`, `recovery_engine_version`,
`parser_version`, `source_offset`, and `source_length` are likewise added
beyond Section 50's terse field list, all directly required by the Phase
10 task's own "RECOVERY OUTPUT" field list.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.recovery import RecoveryMethod, RecoveryStatus
from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.evidence import Evidence
    from app.models.recording import Recording

__all__ = ["RecoveryMethod", "RecoveryResult", "RecoveryStatus"]


class RecoveryResult(Base):
    """One recovery attempt's full, persisted outcome."""

    __tablename__ = "recovery_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recording_id: Mapped[int] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("artifacts.id"), nullable=True, index=True
    )
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    fragments_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fragments_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fragments_missing: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frames_expected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frames_recovered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recovery_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Always NULL in Phase 10: computing a genuine timestamp error requires
    # normalized/validated timestamps, which is Phase 11 ("Timestamp
    # Normalization") territory. The column exists now because it is part
    # of the Section 50 schema; Phase 11 is the phase that may populate it.
    timestamp_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_continuity: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_offset: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_length: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    recovery_engine_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    evidence: Mapped[Evidence] = relationship("Evidence", back_populates="recovery_results")
    recording: Mapped[Recording] = relationship("Recording", back_populates="recovery_results")
    artifact: Mapped[Artifact | None] = relationship("Artifact")

    def __repr__(self) -> str:
        return (
            f"<RecoveryResult recording_id={self.recording_id!r} method={self.method!r} "
            f"status={self.status!r}>"
        )
