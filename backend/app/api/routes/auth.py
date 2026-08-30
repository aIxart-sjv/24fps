"""
API routes for authentication (Phase 21, Part A).

Deliberately minimal: `POST /api/v1/auth/login` and `GET
/api/v1/auth/me`. No registration route -- user provisioning is a
manager-level operation (`app.core.auth_manager.AuthManager.create_user`),
not an HTTP-exposed one (see that module's docstring).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.auth_manager import AuthManager
from app.models import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, LoginResponse
from app.storage.db import get_db

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Authenticate with username/password and receive a short-lived session token."""
    user = AuthManager.authenticate(db, username=payload.username, password=payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    issued = AuthManager.create_session(db, user)
    return LoginResponse(
        token=issued.raw_token,
        expires_at=issued.session.expires_at,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role.value,
    )


@router.get("/auth/me", response_model=CurrentUserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    """Return the identity resolved from the caller's bearer token."""
    return CurrentUserResponse(
        user_id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        role=current_user.role.value,
    )
