"""
SQLAlchemy ORM model for authenticated human users (Phase 21, "Physical
Chain of Custody + QR Handoff").

============================================================================
AUTHENTICATION GAP ASSESSMENT (task Phase 21 scope section 1)
============================================================================
Before writing this model, the existing codebase (Phases 1-20) was
inspected for: user accounts, authentication, a session/token/JWT
mechanism, password handling, a role model, officer identity, lab
identity. **None exist.** `app.audit.events.ActorType` (Phase 15) has
exactly two values, `HUMAN`/`SYSTEM` -- a coarse label an *automated
process* attaches to a `ProcessingEvent` it is recording (task Phase 15
scope section 5: "Never claim an automated process was performed by a
human"), never itself an authenticated identity a caller proves
possession of. `app.audit.events.ActorType`/`ProcessingEvent.actor`
(a free-text string) remain exactly as they were -- this model does not
touch them (see this file's own final section, "Relationship to Phase
15's actor concept").

`frontend/src/lib/auth.ts` is an explicitly-labeled mock ("Frontend-only
mock authentication... There is no backend behind this") with no real
identity behind it at all.

This confirms the task's own expectation: no suitable authentication
system exists to extend. `User` (this model), `UserSession`
(`app.models.auth_session`), `app.security.passwords`/`app.security.
tokens`, and `app.core.auth_manager` together are the smallest
boundary genuinely required for secure QR custody handoff -- not a
general-purpose identity platform. There is no self-service
registration endpoint, no password-reset flow, no email verification,
no OAuth/SSO integration, and no admin user-management API; user
provisioning is a manager-level operation only (see `app.core.
auth_manager.AuthManager.create_user`), documented as a deployment-time/
operational concern, not exposed over HTTP in this phase.

============================================================================
RELATIONSHIP TO PHASE 15'S ACTOR CONCEPT
============================================================================
Kept deliberately separate (task Phase 21 scope section 2: "Do not
confuse Phase 15 automated actors with human authenticated users. Keep
human identity separate from machine/process actors."):
- `ProcessingEvent.actor`/`.actor_type` (Phase 15): a free-text label a
  *system component* stamps onto a provenance record it writes about
  itself or about a human's already-established action -- never proof of
  identity, never authenticated.
- `User` (this model): a real authenticated principal that logs in with a
  password and is issued a session token by `app.core.auth_manager`.

The two connect only at the point a completed custody transfer is
recorded as a `ProcessingEvent`: `app.core.custody_manager.
CustodyManager` passes the *authenticated* `User`'s display identity as
`actor` and `ActorType.HUMAN` as `actor_type` -- reusing Phase 15's
existing vocabulary and recording path unchanged, never inventing a
second provenance mechanism.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.auth_session import UserSession

__all__ = ["User", "UserRole"]


class UserRole(str, Enum):
    """Coarse identity classification for an authenticated human user
    (task Phase 21 scope section 4: "distinguish: normal authenticated
    user, authorized evidence custodian, laboratory personnel where
    applicable, administrator/system").

    "Authorized evidence custodian" is deliberately *not* a role value
    here -- it is dynamic, per-evidence state derived from custody
    history (`app.core.custody_manager.CustodyManager.
    get_current_custodian`), not a fixed property of a user account (task
    Phase 21 scope section 6: current custodian must come from history,
    never a static flag). "System/service" is Phase 15's existing
    `ActorType.SYSTEM` -- automated processes are not `User` rows at all,
    so no `SYSTEM` value is listed here.
    """

    OFFICER = "officer"
    LAB_PERSONNEL = "lab_personnel"
    ADMIN = "admin"


class User(Base):
    """An authenticated human principal (officer, lab personnel, or
    administrator) -- never an automated process (see module docstring).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, native_enum=False), nullable=False, default=UserRole.OFFICER
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    sessions: Mapped[list[UserSession]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User username={self.username!r} role={self.role.value!r}>"
