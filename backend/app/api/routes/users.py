"""
API routes for the user directory (Phase 23).

Phase 23 gap assessment: `app.core.auth_manager.AuthManager.create_user`
existed as a manager-level-only operation (task Phase 21 scope: "not an
enormous general-purpose identity platform... no admin user-management
API"), and nothing at all listed existing users. Two real frontend
requirements need this:

- the physical-custody handoff flow (task Phase 23 scope, "Physical
  Chain of Custody": "select authenticated recipient") needs to enumerate
  real `User` accounts to pick a receiving officer.
- the admin personnel view needs a real user directory instead of a
  mock array.

`POST /users` remains gated to `UserRole.ADMIN` -- still no public
self-service registration, matching Phase 21's own explicit boundary.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.auth_manager import AuthManager
from app.models import User, UserRole
from app.schemas.user import UserCreateRequest, UserResponse
from app.storage.db import get_db

router = APIRouter()


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserResponse]:
    """List every user account. Requires authentication; open to any
    authenticated role (no password/session data is ever included)."""
    del current_user
    return [UserResponse.model_validate(u) for u in AuthManager.list_users(db)]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Provision a new user account. Admin-only."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only an administrator may provision new user accounts",
        )
    try:
        user = AuthManager.create_user(
            db,
            username=payload.username,
            display_name=payload.display_name,
            password=payload.password,
            role=payload.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserResponse.model_validate(user)
