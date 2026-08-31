"""
Pydantic schemas for case-level access grants (Phase 25).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CaseAccessResponse(BaseModel):
    """One (user, case) access grant, current state."""

    id: int
    case_id: int
    case_business_id: str
    user_id: int
    username: str
    user_display_name: str
    status: str
    granted_by_user_id: int
    granted_by_display_name: str
    granted_at: datetime
    revoked_at: datetime | None
    revoked_by_user_id: int | None
    revoked_by_display_name: str | None
    reason: str | None


class CaseAccessGrantRequest(BaseModel):
    """Optional context for a grant/revoke action -- never an identity
    field (task section 25: the acting admin always comes from the
    authenticated session, never from the request body)."""

    reason: str | None = Field(default=None, max_length=1000)


class AccessMatrixCase(BaseModel):
    """One case column header in the admin access matrix."""

    id: int
    case_id: str
    name: str


class AccessMatrixUserRow(BaseModel):
    """One user's row in the admin access matrix: identity plus, for
    every case in the matrix, whether that user currently has active
    access (`ADMIN` rows are always all-`True`, reflecting their
    unconditional visibility -- never a per-case grant row for them)."""

    user_id: int
    username: str
    display_name: str
    role: str
    access_by_case_id: dict[int, bool]


class AccessMatrixResponse(BaseModel):
    """The full admin case-access matrix: every user x every case, built
    from a small number of joined queries (never one query per cell --
    task section 23)."""

    cases: list[AccessMatrixCase]
    users: list[AccessMatrixUserRow]
