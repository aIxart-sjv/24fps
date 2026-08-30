"""
Shared FastAPI dependencies for authenticated routes (Phase 21, Part A).

`get_current_user` is the single place an HTTP route resolves "who is
calling" -- every custody-mutating route depends on it rather than
trusting any caller-supplied identity field (task Phase 21 scope: "Custody
must never trust a caller-supplied arbitrary string... as proof of
identity"). It reads a bearer token from the `Authorization` header and
resolves it via `app.core.auth_manager.AuthManager.validate_session`,
which is the only code path that checks token hash/expiry/revocation.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth_manager import AuthManager
from app.models import User
from app.storage.db import get_db

__all__ = ["get_current_user"]


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    return token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated caller from the `Authorization: Bearer
    <token>` header.

    Raises:
        HTTPException: 401 if the header is missing/malformed, or the
            token is unknown, expired, revoked, or belongs to a
            deactivated user.
    """
    token = _extract_bearer_token(authorization)
    user = AuthManager.validate_session(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return user
