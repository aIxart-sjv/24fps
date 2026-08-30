"""
SQLAlchemy ORM model for derived forensic artifacts.
Master Specification Section 20 (Media Artifact Model), Section 50 (artifacts table).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence


class Artifact(Base):
    """A derived output produced from evidence (Master Spec Section 20).

    An artifact is never the preserved source evidence itself — it is
    something the backend generated (a forensic image copy, a recovered
    recording, an AI result file, a report). Every artifact points back to
    its parent evidence, and optionally to a parent artifact it was derived
    from, so processing is traceable end to end.
    """

    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("path", name="uq_artifact_path"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("artifacts.id"), nullable=True, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    md5: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    created_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tool_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="registered")

    evidence: Mapped[Evidence] = relationship("Evidence", back_populates="artifacts")
    parent_artifact: Mapped[Artifact | None] = relationship(
        "Artifact", remote_side=[id], back_populates="child_artifacts"
    )
    child_artifacts: Mapped[list[Artifact]] = relationship(
        "Artifact", back_populates="parent_artifact"
    )

    def __repr__(self) -> str:
        return f"<Artifact artifact_type={self.artifact_type!r} path={self.path!r}>"
