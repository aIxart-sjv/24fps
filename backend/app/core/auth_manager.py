"""
Business logic for user authentication and session management (Phase 21,
"Physical Chain of Custody + QR Handoff" -- Part A).

DB-aware orchestration layer built on the pure `app.security.passwords`/
`app.security.tokens` primitives, mirroring every prior phase's
pure-primitive/manager split. This is the smallest authentication
boundary the task requires (see `app.models.user`'s module docstring for
the full "Authentication Gap Assessment"): login, session issuance,
session validation. There is deliberately no self-service registration,
password reset, or admin user-management HTTP surface -- `create_user`
is a manager-level operation only, documented as a deployment-time
concern (task Phase 21 scope: "not an enormous general-purpose identity
platform").

Never logs a raw password or raw session token. `authenticate` returns
`None` (never raises) on any invalid-credential path, and takes the same
code path (a real bcrypt comparison) whether the username exists or not,
so a caller cannot distinguish "unknown user" from "wrong password" by
timing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserRole, UserSession
from app.security import generate_token, hash_password, hash_token, verify_password

__all__ = ["AuthManager", "IssuedSession"]

#: A fixed bcrypt hash of no real password, used only to keep
#: `authenticate`'s runtime shape identical whether or not `username`
#: exists -- `verify_password` against a random unknown user still does
#: a real bcrypt comparison rather than short-circuiting immediately.
_DUMMY_HASH = hash_password("no-such-user-dummy-password")


@dataclass(frozen=True)
class IssuedSession:
    """A freshly created session: the persisted row plus the one-time raw
    bearer token (never persisted -- see `UserSession`'s own docstring)."""

    session: UserSession
    raw_token: str


class AuthManager:
    """Service layer for user provisioning, login, and session validation."""

    # ---- Provisioning (manager-level only; no HTTP registration route) --

    @staticmethod
    def create_user(
        db: Session,
        *,
        username: str,
        display_name: str,
        password: str,
        role: UserRole = UserRole.OFFICER,
    ) -> User:
        """Create one authenticated human user.

        Args:
            db: Database session.
            username: Unique login identifier.
            display_name: Human-readable name for provenance/audit display.
            password: Plaintext password -- hashed immediately with
                bcrypt (`app.security.passwords.hash_password`); never
                stored or logged in plaintext.
            role: Coarse role classification (`UserRole`).

        Returns:
            The created, persisted `User`.

        Raises:
            ValueError: If `username` is already taken, or if `password`
                is empty.
        """
        if not password:
            raise ValueError("password must not be empty")
        if db.query(User).filter(User.username == username).first() is not None:
            raise ValueError(f"username {username!r} is already taken")

        user = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def list_users(db: Session) -> list[User]:
        """List every user account, ordered by primary key.

        Read-only; never exposes `password_hash` (callers project this
        into a response schema that omits it). Phase 23 addition: the
        custody-handoff recipient picker and the admin personnel view
        both need to enumerate real accounts -- neither existed as an
        HTTP-reachable capability before (`create_user` was manager-level
        only; nothing listed existing users at all).
        """
        return db.query(User).order_by(User.id).all()

    # ---- Login / session issuance ----------------------------------------

    @staticmethod
    def authenticate(db: Session, *, username: str, password: str) -> User | None:
        """Verify a username/password pair.

        Returns:
            The matching, active `User` on success; `None` on any
            failure (unknown username, wrong password, or a deactivated
            account) -- never distinguishes these to the caller.
        """
        user = db.query(User).filter(User.username == username).first()
        password_hash = user.password_hash if user is not None else _DUMMY_HASH
        password_ok = verify_password(password, password_hash)

        if user is None or not user.is_active or not password_ok:
            return None
        return user

    @staticmethod
    def create_session(db: Session, user: User) -> IssuedSession:
        """Issue one new short-lived session for an already-authenticated user.

        The raw token is returned exactly once, here -- only its SHA-256
        hash (`app.security.tokens.hash_token`) is persisted (see
        `UserSession`'s module docstring).
        """
        settings = get_settings()
        raw_token = generate_token()
        session = UserSession(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.auth_session_ttl_minutes),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return IssuedSession(session=session, raw_token=raw_token)

    @staticmethod
    def revoke_session(db: Session, raw_token: str) -> bool:
        """Explicitly end one session (logout) before its natural expiry.

        Returns:
            `True` if an active session matching the token was found and
            revoked; `False` if the token is unknown, already revoked,
            or already expired.
        """
        session = (
            db.query(UserSession).filter(UserSession.token_hash == hash_token(raw_token)).first()
        )
        if session is None or session.revoked_at is not None:
            return False
        session.revoked_at = datetime.now(UTC)
        db.commit()
        return True

    # ---- Session validation (used by the FastAPI auth dependency) -------

    @staticmethod
    def validate_session(db: Session, raw_token: str) -> User | None:
        """Resolve a bearer token to its authenticated user.

        Returns:
            The session's `User` if the token matches a real, non-revoked,
            unexpired session for an active user; `None` otherwise (never
            raises -- an invalid token is simply "not authenticated").
        """
        if not raw_token:
            return None
        session = (
            db.query(UserSession).filter(UserSession.token_hash == hash_token(raw_token)).first()
        )
        if session is None:
            return None
        if session.revoked_at is not None:
            return None
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return None
        if not session.user.is_active:
            return None
        return session.user
