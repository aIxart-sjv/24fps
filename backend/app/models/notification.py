"""
SQLAlchemy ORM model for officer notifications (Phase 22, "Automatic
Evidence Processing, Findings & Officer Notifications").

A `Notification` never duplicates a `Finding`'s content (task Phase 22
scope, "Notification Model": "Notification points to the authoritative
finding") -- it is a thin per-recipient pointer plus read/acknowledged
state, matching the polling-friendly inbox model the phase scope
explicitly allows in the absence of any existing event bus/websocket/SSE
mechanism in this codebase (none was found during the Phase 22 gap
assessment).

Reuses Phase 21's `User` for `recipient_user_id` -- no second identity
concept, no separate authorization system.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.finding import Finding
    from app.models.user import User

__all__ = ["Notification"]


class Notification(Base):
    """One officer-facing pointer to a `Finding` requiring attention."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recipient: Mapped[User] = relationship("User")
    finding: Mapped[Finding] = relationship("Finding", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification recipient_user_id={self.recipient_user_id} finding_id={self.finding_id}>"
