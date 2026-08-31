"""
SQLAlchemy ORM model for case-level access grants (Phase 25, "Case-Level
Access Control / Admin Permission Matrix").

============================================================================
GAP ASSESSMENT (task Phase 25 scope section 1)
============================================================================
Before writing this model, the existing authorization surface was
inspected: `app.api.deps.get_current_user` resolves *who* is calling
(Phase 21), and `UserRole` (`app.models.user`) classifies that caller as
`OFFICER`/`LAB_PERSONNEL`/`ADMIN`. Neither says anything about *which
cases* that caller may see -- `app/api/routes/cases.py`'s own module
docstring already documented this exact gap explicitly ("Every
authenticated user can still see every case... no case/officer assignment
model exists anywhere in this backend") and the frontend's admin
"Clearance & Matrix" screen (`AdminAccessControl.tsx`) disclosed it
in-UI rather than faking one. This model, plus
`app.core.case_authorization_service.CaseAuthorizationService`, is that
missing case-assignment mechanism -- the smallest one genuinely required:
one row per (user, case) grant, never a general-purpose ACL/permissions
engine, never a duplicate of `Case`/`User` identity.

`ROLE` (`UserRole`) and `CASE ACCESS` (this table) are kept strictly
separate concepts (task section 15): a role is a fixed property of a user
account; case access is dynamic, per-(user, case) state, exactly mirroring
how `app.models.user`'s own docstring already drew this same distinction
for "authorized evidence custodian" vs. a fixed role. `ADMIN` is not a row
in this table at all -- admin case visibility is unconditional and derived
from `UserRole.ADMIN` directly (`CaseAuthorizationService.can_view_case`),
never encoded as "an admin who happens to have every case granted" (task
section 3: "cannot be accidentally restricted by a normal case
assignment").
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.user import User

__all__ = ["CaseAccessStatus", "CaseUserAccess"]


class CaseAccessStatus(str, Enum):
    """Whether one (user, case) grant is currently in effect.

    Two values only -- this is a binary "can this officer currently open
    this case" state, never a multi-level clearance scheme (task section
    15: "Do NOT claim OFFICER = L1 ... unless those clearance levels are
    genuinely implemented and enforced" -- none are, so none are modeled).
    """

    ACTIVE = "active"
    REVOKED = "revoked"


class CaseUserAccess(Base):
    """One (user, case) access grant -- exactly one row per pair, ever.

    Deliberately mutable in place, not append-only: unlike
    `ProcessingEvent` (Phase 15, append-only by design so the audit chain
    is tamper-evident), the *history* of who granted/revoked access when
    is not this table's job -- it lives in the existing hash-linked
    `ProcessingEvent` audit chain instead (task section 10/11: "Use the
    existing ProcessingEvent/ProvenanceManager/AuditChainManager
    architecture... do NOT create a separate logging system"). This table
    only ever needs to answer "is user X currently allowed into case Y",
    for which one row toggled between `ACTIVE`/`REVOKED` (and re-grantable
    without ever violating the unique constraint below) is the correct,
    simplest shape -- see `CaseAuthorizationService.grant_case_access`/
    `revoke_case_access`, which upsert this single row and separately
    call `ProvenanceManager.record_event` for the auditable history.

    The real uniqueness invariant the task asks for ("prevent duplicate
    active grants... (user_id, case_id)") is enforced here as a genuine,
    always-on DB constraint -- not a partial/conditional index -- exactly
    because there is only ever one row per pair to begin with.
    """

    __tablename__ = "case_user_access"
    __table_args__ = (UniqueConstraint("user_id", "case_id", name="uq_case_user_access_user_case"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[CaseAccessStatus] = mapped_column(
        SQLEnum(CaseAccessStatus, native_enum=False), nullable=False, index=True
    )
    #: Who most recently granted (or re-granted) this access. Never a
    #: caller-supplied identity (task section 25: "the authenticated admin
    #: identity must come from the session") -- always the acting admin's
    #: own `User.id`, resolved server-side from `get_current_user`.
    granted_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    #: Set on the most recent revocation; cleared (`NULL`) again on
    #: re-grant. `NULL` whenever `status == ACTIVE`.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[Case] = relationship("Case", back_populates="user_access_grants")
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    granted_by: Mapped[User] = relationship("User", foreign_keys=[granted_by_user_id])
    revoked_by: Mapped[User | None] = relationship("User", foreign_keys=[revoked_by_user_id])

    def __repr__(self) -> str:
        return (
            f"<CaseUserAccess case_id={self.case_id} user_id={self.user_id} "
            f"status={self.status.value!r}>"
        )
