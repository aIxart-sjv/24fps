"""Tests for app/api/routes/users.py (Phase 23)."""

from __future__ import annotations

from app.core.auth_manager import AuthManager
from app.models import UserRole


def _make_user(db, username: str, role: UserRole = UserRole.OFFICER):
    return AuthManager.create_user(
        db, username=username, display_name=username.title(), password="password123", role=role
    )


def _login(test_client, username: str) -> dict[str, str]:
    resp = test_client.post(
        "/api/v1/auth/login", json={"username": username, "password": "password123"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_list_users_requires_authentication(test_client) -> None:
    resp = test_client.get("/api/v1/users")
    assert resp.status_code == 401


def test_list_users_never_exposes_password_hash(test_db, test_client) -> None:
    _make_user(test_db, "officer_list")
    headers = _login(test_client, "officer_list")

    resp = test_client.get("/api/v1/users", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "password_hash" not in body[0]
    assert "password" not in body[0]
    assert body[0]["username"] == "officer_list"


def test_non_admin_cannot_create_user(test_db, test_client) -> None:
    _make_user(test_db, "officer_plain", role=UserRole.OFFICER)
    headers = _login(test_client, "officer_plain")

    resp = test_client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "new_officer", "display_name": "New Officer", "password": "pw123456"},
    )
    assert resp.status_code == 403


def test_admin_can_create_user(test_db, test_client) -> None:
    _make_user(test_db, "admin_1", role=UserRole.ADMIN)
    headers = _login(test_client, "admin_1")

    resp = test_client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "new_officer", "display_name": "New Officer", "password": "pw123456"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "officer"

    list_resp = test_client.get("/api/v1/users", headers=headers)
    usernames = {u["username"] for u in list_resp.json()}
    assert {"admin_1", "new_officer"} <= usernames


def test_create_user_duplicate_username_400(test_db, test_client) -> None:
    _make_user(test_db, "admin_dup", role=UserRole.ADMIN)
    headers = _login(test_client, "admin_dup")

    resp = test_client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "admin_dup", "display_name": "Dup", "password": "pw123456"},
    )
    assert resp.status_code == 400
