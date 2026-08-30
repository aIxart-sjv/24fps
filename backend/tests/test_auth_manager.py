"""Tests for app/core/auth_manager.py (Phase 21, Part A)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.auth_manager import AuthManager
from app.models import UserRole, UserSession


class TestCreateUser:
    def test_creates_user_with_hashed_password(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db, username="officer1", display_name="Officer One", password="s3cret-pw!"
        )
        assert user.id is not None
        assert user.username == "officer1"
        assert user.password_hash != "s3cret-pw!"
        assert user.role == UserRole.OFFICER
        assert user.is_active is True

    def test_default_role_is_officer(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db, username="u1", display_name="U1", password="password123"
        )
        assert user.role == UserRole.OFFICER

    def test_explicit_role_is_honored(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db,
            username="lab1",
            display_name="Lab One",
            password="password123",
            role=UserRole.LAB_PERSONNEL,
        )
        assert user.role == UserRole.LAB_PERSONNEL

    def test_duplicate_username_rejected(self, test_db) -> None:
        AuthManager.create_user(test_db, username="dup", display_name="Dup", password="password123")
        with pytest.raises(ValueError, match="already taken"):
            AuthManager.create_user(
                test_db, username="dup", display_name="Dup2", password="password456"
            )

    def test_empty_password_rejected(self, test_db) -> None:
        with pytest.raises(ValueError, match="empty"):
            AuthManager.create_user(test_db, username="nopass", display_name="No Pass", password="")


class TestAuthenticate:
    def test_valid_credentials_return_user(self, test_db) -> None:
        AuthManager.create_user(
            test_db, username="alice", display_name="Alice", password="correct-password"
        )
        user = AuthManager.authenticate(test_db, username="alice", password="correct-password")
        assert user is not None
        assert user.username == "alice"

    def test_wrong_password_returns_none(self, test_db) -> None:
        AuthManager.create_user(
            test_db, username="bob", display_name="Bob", password="correct-password"
        )
        assert AuthManager.authenticate(test_db, username="bob", password="wrong") is None

    def test_unknown_username_returns_none(self, test_db) -> None:
        assert AuthManager.authenticate(test_db, username="ghost", password="anything") is None

    def test_deactivated_user_cannot_authenticate(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db, username="deact", display_name="Deact", password="correct-password"
        )
        user.is_active = False
        test_db.commit()
        assert (
            AuthManager.authenticate(test_db, username="deact", password="correct-password") is None
        )


class TestSessionLifecycle:
    def test_create_session_returns_raw_token_once(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db, username="carol", display_name="Carol", password="correct-password"
        )
        issued = AuthManager.create_session(test_db, user)
        assert len(issued.raw_token) > 20
        assert issued.session.token_hash != issued.raw_token
        # Only the hash is persisted.
        stored = test_db.query(UserSession).filter(UserSession.id == issued.session.id).first()
        assert stored is not None
        assert stored.token_hash == issued.session.token_hash

    def test_validate_session_resolves_correct_user(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db, username="dave", display_name="Dave", password="correct-password"
        )
        issued = AuthManager.create_session(test_db, user)
        resolved = AuthManager.validate_session(test_db, issued.raw_token)
        assert resolved is not None
        assert resolved.id == user.id

    def test_validate_session_rejects_unknown_token(self, test_db) -> None:
        assert AuthManager.validate_session(test_db, "not-a-real-token") is None

    def test_validate_session_rejects_empty_token(self, test_db) -> None:
        assert AuthManager.validate_session(test_db, "") is None

    def test_validate_session_rejects_expired_session(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db, username="eve", display_name="Eve", password="correct-password"
        )
        issued = AuthManager.create_session(test_db, user)
        issued.session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        test_db.commit()
        assert AuthManager.validate_session(test_db, issued.raw_token) is None

    def test_revoke_session_invalidates_it(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db, username="frank", display_name="Frank", password="correct-password"
        )
        issued = AuthManager.create_session(test_db, user)
        assert AuthManager.revoke_session(test_db, issued.raw_token) is True
        assert AuthManager.validate_session(test_db, issued.raw_token) is None

    def test_revoke_unknown_token_returns_false(self, test_db) -> None:
        assert AuthManager.revoke_session(test_db, "no-such-token") is False

    def test_revoke_already_revoked_returns_false(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db, username="gina", display_name="Gina", password="correct-password"
        )
        issued = AuthManager.create_session(test_db, user)
        assert AuthManager.revoke_session(test_db, issued.raw_token) is True
        assert AuthManager.revoke_session(test_db, issued.raw_token) is False

    def test_validate_session_rejects_deactivated_users_session(self, test_db) -> None:
        user = AuthManager.create_user(
            test_db, username="hank", display_name="Hank", password="correct-password"
        )
        issued = AuthManager.create_session(test_db, user)
        user.is_active = False
        test_db.commit()
        assert AuthManager.validate_session(test_db, issued.raw_token) is None
