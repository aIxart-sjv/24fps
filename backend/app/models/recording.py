"""
SQLAlchemy ORM model for video recordings extracted from evidence.
Master Specification Section 50.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.metadata import RecordingMetadata
    from app.models.recovery import RecoveryResult


class Recording(Base):
    """Video recording extracted or recovered from evidence."""

    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recording_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    channel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_original: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_original: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_normalized: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_normalized: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    container: Mapped[str | None] = mapped_column(String(64), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(nullable=True)
    source_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recovery_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    evidence: Mapped[Evidence] = relationship("Evidence", back_populates="recordings")
    # Named `metadata_entries`, not `metadata`: SQLAlchemy's declarative
    # `Base` reserves the `metadata` attribute name for its own `MetaData`
    # instance (Phase 9, Master Specification Section 50's `metadata` table).
    metadata_entries: Mapped[list[RecordingMetadata]] = relationship(
        "RecordingMetadata", back_populates="recording", cascade="all, delete-orphan"
    )
    recovery_results: Mapped[list[RecoveryResult]] = relationship(
        "RecoveryResult", back_populates="recording", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Recording recording_id={self.recording_id!r} camera_id={self.camera_id!r}>"
