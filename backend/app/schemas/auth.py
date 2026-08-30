"""
Pydantic schemas for authentication (Phase 21, Part A).

`POST /api/v1/auth/login` is the only authentication HTTP route (see
`app.core.auth_manager`'s module docstring for why there is deliberately
no self-service registration/password-reset schema here).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Username/password login credentials."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """A newly issued session. `token` is the raw bearer token -- present
    exactly once, here; only its hash is ever persisted (see
    `app.models.auth_session.UserSession`'s module docstring)."""

    token: str
    expires_at: datetime
    user_id: int
    username: str
    display_name: str
    role: str


class CurrentUserResponse(BaseModel):
    """The identity of the caller resolved from their bearer token."""

    user_id: int
    username: str
    display_name: str
    role: str
