"""
SQLAlchemy ORM model for evidence items.
Master Specification Section 8, 50.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.case import Case
    from app.models.device import Device
    from app.models.hash import EvidenceHash
    from app.models.recording import Recording
    from app.models.recovery import RecoveryResult
    from app.models.storage import Storage


class Evidence(Base):
    """Individual evidence item within a case."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="registered")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    case: Mapped[Case] = relationship("Case", back_populates="evidence_list")
    device: Mapped[Device | None] = relationship("Device", back_populates="evidence", uselist=False)
    storage: Mapped[Storage | None] = relationship(
        "Storage", back_populates="evidence", uselist=False
    )
    recordings: Mapped[list[Recording]] = relationship("Recording", back_populates="evidence")
    hashes: Mapped[list[EvidenceHash]] = relationship("EvidenceHash", back_populates="evidence")
    artifacts: Mapped[list[Artifact]] = relationship("Artifact", back_populates="evidence")
    recovery_results: Mapped[list[RecoveryResult]] = relationship(
        "RecoveryResult", back_populates="evidence"
    )

    def __repr__(self) -> str:
        return f"<Evidence evidence_id={self.evidence_id!r} source_type={self.source_type!r}>"
