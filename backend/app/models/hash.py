"""
SQLAlchemy ORM model for evidence integrity hashes.
Master Specification Section 38 (Integrity Engine), Section 50 (hashes table).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence


class HashAlgorithm(str, Enum):
    """Supported integrity hash algorithms."""

    SHA256 = "sha256"
    MD5 = "md5"


class VerificationStatus(str, Enum):
    """Verification state of a stored hash against a recomputed value."""

    NOT_VERIFIED = "not_verified"
    VERIFIED = "verified"
    MISMATCH = "mismatch"


class EvidenceHash(Base):
    """A stored integrity hash for an evidence item."""

    __tablename__ = "evidence_hashes"
    __table_args__ = (
        UniqueConstraint("evidence_id", "algorithm", name="uq_evidence_hash_algorithm"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    algorithm: Mapped[HashAlgorithm] = mapped_column(
        SQLEnum(HashAlgorithm, native_enum=False), nullable=False
    )
    hash_value: Mapped[str] = mapped_column(String(128), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    software_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(VerificationStatus, native_enum=False),
        nullable=False,
        default=VerificationStatus.NOT_VERIFIED,
    )

    evidence: Mapped[Evidence] = relationship("Evidence", back_populates="hashes")

    def __repr__(self) -> str:
        return f"<EvidenceHash evidence_id={self.evidence_id} algorithm={self.algorithm.value!r}>"
