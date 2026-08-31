"""Tests for POST /auth/logout (Phase 23)."""

from __future__ import annotations

from app.core.auth_manager import AuthManager


def _make_user(db, username: str = "officer_logout"):
    return AuthManager.create_user(
        db, username=username, display_name="Officer Logout", password="password123"
    )


def test_logout_revokes_session_and_it_can_no_longer_be_used(test_db, test_client) -> None:
    _make_user(test_db)
    login_resp = test_client.post(
        "/api/v1/auth/login", json={"username": "officer_logout", "password": "password123"}
    )
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = test_client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200

    logout_resp = test_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 204

    me_after_resp = test_client.get("/api/v1/auth/me", headers=headers)
    assert me_after_resp.status_code == 401


def test_logout_with_unknown_token_is_idempotent(test_client) -> None:
    resp = test_client.post(
        "/api/v1/auth/logout", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 204


def test_logout_without_header_401(test_client) -> None:
    resp = test_client.post("/api/v1/auth/logout")
    assert resp.status_code == 401
