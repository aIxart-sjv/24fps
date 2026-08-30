"""
SQLAlchemy ORM model for DVR/NVR device information.
Master Specification Section 50.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence


class Device(Base):
    """Detected DVR/NVR device information."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    vendor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    firmware: Mapped[str | None] = mapped_column(String(128), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    camera_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    network_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    identification_method: Mapped[str | None] = mapped_column(String(128), nullable=True)

    evidence: Mapped[Evidence] = relationship("Evidence", back_populates="device")

    def __repr__(self) -> str:
        return f"<Device vendor={self.vendor!r} model={self.model!r}>"
