"""
Pydantic schemas for user directory / provisioning (Phase 23).

`UserResponse` never includes `password_hash` -- the same "never expose
the hash" discipline `CustodyTransferResponse` already documents for
`token_hash`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class UserResponse(BaseModel):
    """One user account, safe to return to any authenticated caller."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserCreateRequest(BaseModel):
    """Request to provision a new user account. Admin-only (task Phase 23
    scope, "User provisioning is a manager-level operation" -- this is
    the minimal HTTP surface for that, gated to `UserRole.ADMIN`, not a
    public self-service registration route)."""

    username: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=256)
    password: str = Field(..., min_length=1)
    role: UserRole = UserRole.OFFICER
