"""
SQLAlchemy ORM model for forensic cases.
Master Specification Section 7, 50.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.ai_result import AIResult, AITrack, MotionEvent
    from app.models.audit import ProcessingEvent
    from app.models.blockchain import BlockchainAnchor
    from app.models.case_access import CaseUserAccess
    from app.models.evidence import Evidence
    from app.models.job import Job
    from app.models.report import Report
    from app.models.timeline import TimelineEvent
    from app.models.validation import GroundTruth, ValidationMetric


class CaseStatus(str, Enum):
    """Possible states of a forensic case."""

    DRAFT = "draft"
    ACTIVE = "active"
    PROCESSING = "processing"
    REVIEW = "review"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Case(Base):
    """Top-level investigation container."""

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    case_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    examiner: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    reference_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[CaseStatus] = mapped_column(
        SQLEnum(CaseStatus, native_enum=False), nullable=False, default=CaseStatus.DRAFT
    )
    software_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(32), nullable=True, default="1.0")

    evidence_list: Mapped[list[Evidence]] = relationship(
        "Evidence", back_populates="case", cascade="save-update, merge"
    )
    timeline_events: Mapped[list[TimelineEvent]] = relationship(
        "TimelineEvent", back_populates="case", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[Job]] = relationship(
        "Job", back_populates="case", cascade="all, delete-orphan"
    )
    ai_results: Mapped[list[AIResult]] = relationship(
        "AIResult", back_populates="case", cascade="all, delete-orphan"
    )
    ai_tracks: Mapped[list[AITrack]] = relationship(
        "AITrack", back_populates="case", cascade="all, delete-orphan"
    )
    motion_events: Mapped[list[MotionEvent]] = relationship(
        "MotionEvent", back_populates="case", cascade="all, delete-orphan"
    )
    ground_truth_records: Mapped[list[GroundTruth]] = relationship(
        "GroundTruth", back_populates="case", cascade="all, delete-orphan"
    )
    validation_metrics: Mapped[list[ValidationMetric]] = relationship(
        "ValidationMetric", back_populates="case", cascade="all, delete-orphan"
    )
    processing_events: Mapped[list[ProcessingEvent]] = relationship(
        "ProcessingEvent", back_populates="case", cascade="all, delete-orphan"
    )
    blockchain_anchors: Mapped[list[BlockchainAnchor]] = relationship(
        "BlockchainAnchor", back_populates="case", cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(
        "Report", back_populates="case", cascade="all, delete-orphan"
    )
    user_access_grants: Mapped[list[CaseUserAccess]] = relationship(
        "CaseUserAccess",
        back_populates="case",
        cascade="all, delete-orphan",
        foreign_keys="CaseUserAccess.case_id",
    )

    def __repr__(self) -> str:
        return f"<Case case_id={self.case_id!r} name={self.name!r}>"
