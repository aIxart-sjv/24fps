"""
SQLAlchemy ORM model for authenticated user sessions (Phase 21).

`app.core.auth_manager.AuthManager` is the sole writer. Only
`token_hash` (never the raw bearer token) is stored -- see
`app.security.tokens`'s module docstring for why a fast SHA-256 hash is
the correct (not merely convenient) choice here, unlike password
storage. A session is looked up by hashing the bearer token presented on
each request and comparing against this column; the raw token exists
only in the HTTP response at login time and in the caller's own
`Authorization` header afterward, never at rest in this database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.user import User

__all__ = ["UserSession"]


class UserSession(Base):
    """One issued, short-lived authenticated session.

    Append-oriented in the same spirit as `ProcessingEvent` (Phase 15):
    a session is created once at login and only ever transitions to
    "revoked" (explicit logout) after that -- `expires_at` is a fixed
    value set at creation, never extended/rewritten by later requests
    ("sliding" session expiry would make a compromised token's real
    lifetime unbounded, undermining the "short-lived" requirement).
    """

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<UserSession user_id={self.user_id} expires_at={self.expires_at!r}>"
