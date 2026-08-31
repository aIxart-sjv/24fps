"""HTTP-level tests for app/api/routes/auth.py and
app/api/routes/custody.py (Phase 21, Part A).

Uses the shared `test_db` (direct DB setup) and `test_client` (HTTP)
fixtures together -- both are bound to the same in-memory `test_engine`,
so state created directly via `test_db` is visible to requests made
through `test_client`.
"""

from __future__ import annotations

from app.core.auth_manager import AuthManager
from app.core.case_authorization_service import CaseAuthorizationService
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.models import UserRole
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest


def _make_case_and_evidence(db, case_id: str = "CASE-API-1"):
    case = CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="API test case"))
    evidence = EvidenceManager.register_evidence(
        db,
        case_id=case.id,
        request=EvidenceCreateRequest(
            evidence_id=f"{case_id}-EV-1", source_type="disk_image", source_description="disk"
        ),
    )
    return case, evidence


def _make_user(db, username: str, password: str = "password123", role: UserRole = UserRole.OFFICER):
    return AuthManager.create_user(
        db, username=username, display_name=username.title(), password=password, role=role
    )


def _grant_case_access(db, case, *users) -> None:
    """Phase 25: custody routes are also case-access-protected now -- grant
    every officer/lab-personnel participant in a custody scenario access
    to the scenario's case, mirroring how they'd have been assigned to it
    by an admin in real use before ever touching physical custody."""
    admin = AuthManager.create_user(
        db,
        username=f"admin_for_{case.case_id}",
        display_name="Access Admin",
        password="password123",
        role=UserRole.ADMIN,
    )
    for user in users:
        CaseAuthorizationService.grant_case_access(db, admin, user_id=user.id, case_id=case.id)


def _auth_headers(test_client, username: str, password: str = "password123") -> dict[str, str]:
    resp = test_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


class TestAuthApi:
    def test_login_success_returns_token(self, test_db, test_client) -> None:
        _make_user(test_db, "login_ok")
        resp = test_client.post(
            "/api/v1/auth/login", json={"username": "login_ok", "password": "password123"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "token" in body
        assert body["username"] == "login_ok"

    def test_login_wrong_password_401(self, test_db, test_client) -> None:
        _make_user(test_db, "login_bad")
        resp = test_client.post(
            "/api/v1/auth/login", json={"username": "login_bad", "password": "wrong"}
        )
        assert resp.status_code == 401

    def test_login_unknown_user_401(self, test_client) -> None:
        resp = test_client.post(
            "/api/v1/auth/login", json={"username": "no_such_user", "password": "x"}
        )
        assert resp.status_code == 401

    def test_me_requires_authentication(self, test_client) -> None:
        resp = test_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_rejects_malformed_header(self, test_client) -> None:
        resp = test_client.get("/api/v1/auth/me", headers={"Authorization": "NotBearer xyz"})
        assert resp.status_code == 401

    def test_me_returns_identity_for_valid_token(self, test_db, test_client) -> None:
        _make_user(test_db, "me_user")
        headers = _auth_headers(test_client, "me_user")
        resp = test_client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "me_user"

    def test_expired_session_rejected(self, test_db, test_client) -> None:
        from datetime import UTC, datetime, timedelta

        user = _make_user(test_db, "expired_user")
        issued = AuthManager.create_session(test_db, user)
        issued.session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        test_db.commit()
        resp = test_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {issued.raw_token}"}
        )
        assert resp.status_code == 401


class TestCustodyApiFullLifecycle:
    def test_full_handoff_lifecycle(self, test_db, test_client) -> None:
        case, evidence = _make_case_and_evidence(test_db, "CASE-LIFECYCLE")
        officer_a = _make_user(test_db, "life_a")
        officer_b = _make_user(test_db, "life_b")
        _grant_case_access(test_db, case, officer_a, officer_b)
        headers_a = _auth_headers(test_client, "life_a")
        headers_b = _auth_headers(test_client, "life_b")

        # unauthenticated calls are rejected
        resp = test_client.get(f"/api/v1/evidence/{evidence.id}/custody/current")
        assert resp.status_code == 401

        # intake
        resp = test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/intake",
            json={"receiving_user_id": officer_a.id},
            headers=headers_a,
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "accepted"

        # current custodian
        resp = test_client.get(f"/api/v1/evidence/{evidence.id}/custody/current", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["receiving_user_id"] == officer_a.id

        # initiate handoff
        resp = test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/handoff",
            json={"receiving_user_id": officer_b.id, "location": "Locker 3"},
            headers=headers_a,
        )
        assert resp.status_code == 201
        body = resp.json()
        token = body["token"]
        assert len(body["qr_code_png_base64"]) > 100
        assert body["transfer"]["status"] == "pending"

        # inspect as intended receiver
        resp = test_client.post(
            "/api/v1/custody/handoff/inspect", json={"token": token}, headers=headers_b
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

        # accept
        resp = test_client.post(
            "/api/v1/custody/handoff/accept", json={"token": token}, headers=headers_b
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

        # replay fails
        resp = test_client.post(
            "/api/v1/custody/handoff/accept", json={"token": token}, headers=headers_b
        )
        assert resp.status_code == 400

        # history has 2 entries
        resp = test_client.get(f"/api/v1/evidence/{evidence.id}/custody/history", headers=headers_b)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        # audit chain (Phase 15/16 route) reflects the custody events
        resp = test_client.get(f"/api/v1/cases/{case.id}/audit/verify", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_wrong_receiver_gets_403_and_state_unchanged(self, test_db, test_client) -> None:
        case, evidence = _make_case_and_evidence(test_db, "CASE-WRONG-RCV")
        officer_a = _make_user(test_db, "wr_a")
        officer_b = _make_user(test_db, "wr_b")
        _make_user(test_db, "wr_stranger")
        _grant_case_access(test_db, case, officer_a, officer_b)
        headers_a = _auth_headers(test_client, "wr_a")
        headers_stranger = _auth_headers(test_client, "wr_stranger")

        test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/intake",
            json={"receiving_user_id": officer_a.id},
            headers=headers_a,
        )
        resp = test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/handoff",
            json={"receiving_user_id": officer_b.id},
            headers=headers_a,
        )
        token = resp.json()["token"]

        resp = test_client.post(
            "/api/v1/custody/handoff/accept", json={"token": token}, headers=headers_stranger
        )
        assert resp.status_code == 403

        resp = test_client.post(
            "/api/v1/custody/handoff/inspect", json={"token": token}, headers=headers_stranger
        )
        assert resp.status_code == 403

    def test_non_custodian_cannot_initiate_handoff(self, test_db, test_client) -> None:
        case, evidence = _make_case_and_evidence(test_db, "CASE-NONCUST")
        officer_a = _make_user(test_db, "nc_a")
        _make_user(test_db, "nc_b")
        officer_c = _make_user(test_db, "nc_c")
        headers_a = _auth_headers(test_client, "nc_a")
        headers_b = _auth_headers(test_client, "nc_b")

        test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/intake",
            json={"receiving_user_id": officer_a.id},
            headers=headers_a,
        )
        resp = test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/handoff",
            json={"receiving_user_id": officer_c.id},
            headers=headers_b,
        )
        assert resp.status_code == 403

    def test_malformed_token_returns_400(self, test_db, test_client) -> None:
        _make_user(test_db, "malformed_user")
        headers = _auth_headers(test_client, "malformed_user")
        resp = test_client.post(
            "/api/v1/custody/handoff/accept", json={"token": "not-a-real-token"}, headers=headers
        )
        assert resp.status_code == 400

    def test_cancel_by_non_initiator_403(self, test_db, test_client) -> None:
        case, evidence = _make_case_and_evidence(test_db, "CASE-CANCEL")
        officer_a = _make_user(test_db, "cnl_a")
        officer_b = _make_user(test_db, "cnl_b")
        _grant_case_access(test_db, case, officer_a, officer_b)
        headers_a = _auth_headers(test_client, "cnl_a")
        headers_b = _auth_headers(test_client, "cnl_b")

        test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/intake",
            json={"receiving_user_id": officer_a.id},
            headers=headers_a,
        )
        resp = test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/handoff",
            json={"receiving_user_id": officer_b.id},
            headers=headers_a,
        )
        transfer_id = resp.json()["transfer"]["id"]

        resp = test_client.post(f"/api/v1/custody/handoff/{transfer_id}/cancel", headers=headers_b)
        assert resp.status_code == 403

        resp = test_client.post(f"/api/v1/custody/handoff/{transfer_id}/cancel", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_lab_personnel_can_accept_same_mechanism(self, test_db, test_client) -> None:
        case, evidence = _make_case_and_evidence(test_db, "CASE-LAB-API")
        officer = _make_user(test_db, "lab_api_officer")
        lab_tech = _make_user(test_db, "lab_api_tech", role=UserRole.LAB_PERSONNEL)
        _grant_case_access(test_db, case, officer, lab_tech)
        headers_officer = _auth_headers(test_client, "lab_api_officer")
        headers_lab = _auth_headers(test_client, "lab_api_tech")

        test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/intake",
            json={"receiving_user_id": officer.id},
            headers=headers_officer,
        )
        resp = test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/handoff",
            json={"receiving_user_id": lab_tech.id},
            headers=headers_officer,
        )
        token = resp.json()["token"]

        resp = test_client.post(
            "/api/v1/custody/handoff/accept", json={"token": token}, headers=headers_lab
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"

    def test_reject_leaves_custodian_unchanged(self, test_db, test_client) -> None:
        case, evidence = _make_case_and_evidence(test_db, "CASE-REJECT-API")
        officer_a = _make_user(test_db, "rej_api_a")
        officer_b = _make_user(test_db, "rej_api_b")
        _grant_case_access(test_db, case, officer_a, officer_b)
        headers_a = _auth_headers(test_client, "rej_api_a")
        headers_b = _auth_headers(test_client, "rej_api_b")

        test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/intake",
            json={"receiving_user_id": officer_a.id},
            headers=headers_a,
        )
        resp = test_client.post(
            f"/api/v1/evidence/{evidence.id}/custody/handoff",
            json={"receiving_user_id": officer_b.id},
            headers=headers_a,
        )
        token = resp.json()["token"]

        resp = test_client.post(
            "/api/v1/custody/handoff/reject", json={"token": token}, headers=headers_b
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        resp = test_client.get(f"/api/v1/evidence/{evidence.id}/custody/current", headers=headers_a)
        assert resp.json()["receiving_user_id"] == officer_a.id
