"""
SQLAlchemy ORM model for storage device information.
Master Specification Section 50.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence


class Storage(Base):
    """Storage device metadata associated with evidence."""

    __tablename__ = "storage_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    manufacturer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capacity_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sector_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interface: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_only: Mapped[bool | None] = mapped_column(nullable=True, default=False)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    evidence: Mapped[Evidence] = relationship("Evidence", back_populates="storage")

    def __repr__(self) -> str:
        return f"<Storage manufacturer={self.manufacturer!r} model={self.model!r}>"
