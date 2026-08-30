"""
SQLAlchemy ORM model for recording metadata.
Master Specification Section 50 ("Database Model"): `TABLE: metadata (id,
recording_id, key, value, source, confidence)`, with the explicit design
note "If frequently queried fields become stable, promote them into typed
columns rather than putting everything into a key/value table."

Phase 9 ("Recording extraction + FFmpeg") uses this table for exactly that
purpose: extraction status/warnings, the ordered list of source CPV
segments a session `Recording` was built from, session-link status, raw
(unvalidated) timestamp provenance, and derived-artifact cross-references
that do not have — and, per Section 50's own design note, should not yet
have — a dedicated column on `recordings`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.recording import Recording


class RecordingMetadata(Base):
    """One key/value metadata entry attached to a `Recording`.

    `value` is free-text; structured values (e.g. an ordered list of
    source segments) are JSON-encoded by the writer and decoded by the
    reader — this table itself stays schema-agnostic, per Section 50.
    """

    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    recording_id: Mapped[int] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    recording: Mapped[Recording] = relationship("Recording", back_populates="metadata_entries")

    def __repr__(self) -> str:
        return f"<RecordingMetadata recording_id={self.recording_id!r} key={self.key!r}>"
