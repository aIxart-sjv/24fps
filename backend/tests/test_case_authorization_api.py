"""HTTP-level tests for Phase 25 ("Case-Level Access Control / Admin
Permission Matrix"): the admin matrix/grant/revoke API, and -- the
critical part -- that every case-scoped route actually rejects a caller
without access (task sections 16-20: role-policy tests, section 17: every
case-scoped route type, section 18: IDOR, section 19: grant/revoke
end-to-end through real HTTP calls, section 20: multi-officer sequencing).

`_build_full_case` populates one case with one of everything a real case
accumulates (evidence, recording, artifact, AI result, finding, job,
report) so the IDOR sweep below can hit every route type named in task
section 5/17 with a real, resolvable ID -- never a route that 404s before
ever reaching the authorization check it's supposed to be testing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.audit import ActorType, ProcessingOperation
from app.core.auth_manager import AuthManager
from app.core.case_authorization_service import CaseAuthorizationService
from app.core.case_manager import CaseManager
from app.core.job_manager import JobManager
from app.core.provenance_manager import ProvenanceManager
from app.models import (
    AIResult,
    Artifact,
    Evidence,
    Finding,
    JobStatus,
    Recording,
    Report,
    UserRole,
)
from app.schemas.case import CaseCreateRequest

_T0 = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)


@dataclass
class FullCase:
    case_id: int
    evidence_id: int
    recording_id: int
    artifact_id: int
    ai_result_id: int
    finding_id: int
    job_id: int
    report_id: int


def _build_full_case(db, case_business_id: str) -> FullCase:
    case = CaseManager.create_case(
        db, CaseCreateRequest(case_id=case_business_id, name=f"{case_business_id} case")
    )
    evidence = Evidence(
        evidence_id=f"EVID-{case_business_id}", case_id=case.id, source_type="native_export"
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    artifact = Artifact(
        evidence_id=evidence.id,
        artifact_type="cp_plus_h264_preview_mp4",
        path=f"/tmp/{case_business_id}-preview.mp4",
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    recording = Recording(
        evidence_id=evidence.id,
        recording_id=f"REC-{case_business_id}",
        artifact_id=str(artifact.id),
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)

    ai_result = AIResult(
        case_id=case.id,
        recording_id=recording.id,
        analysis_type="object_detection",
        model_name="yolov8n.pt",
        model_version="yolov8n",
        frame_number=0,
        class_name="car",
        confidence=0.9,
        bbox_x_min=0.0,
        bbox_y_min=0.0,
        bbox_x_max=10.0,
        bbox_y_max=10.0,
        source_artifact=artifact.id,
    )
    db.add(ai_result)
    db.commit()
    db.refresh(ai_result)

    finding = Finding(
        case_id=case.id,
        evidence_id=evidence.id,
        recording_id=recording.id,
        finding_type="unsupported_format",
        severity="low",
        confidence="low",
        title="Test finding",
        description="A synthetic finding for IDOR testing.",
        status="open",
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)

    job = JobManager.create_job(db, case_id=case.id, job_type="validation")

    report = Report(
        case_id=case.id,
        report_type="json",
        path=f"/tmp/{case_business_id}-report.json",
        report_schema_version="1.0",
        status="completed",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.PARSING.value,
        actor="TestActor",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )

    return FullCase(
        case_id=case.id,
        evidence_id=evidence.id,
        recording_id=recording.id,
        artifact_id=artifact.id,
        ai_result_id=ai_result.id,
        finding_id=finding.id,
        job_id=job.id,
        report_id=report.id,
    )


def _make_user(db, username: str, role: UserRole = UserRole.OFFICER):
    return AuthManager.create_user(
        db, username=username, display_name=username.title(), password="password123", role=role
    )


def _login(test_client, username: str, password: str = "password123") -> dict[str, str]:
    resp = test_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# =============================================================================
# Section 16: role-policy tests
# =============================================================================


class TestRolePolicy:
    def test_admin_can_see_all_cases(self, test_db, test_client) -> None:
        _make_user(test_db, "role_admin_1", role=UserRole.ADMIN)
        _build_full_case(test_db, "ROLE-ADMIN-A")
        _build_full_case(test_db, "ROLE-ADMIN-B")
        headers = _login(test_client, "role_admin_1")

        resp = test_client.get("/api/v1/cases", headers=headers)
        assert resp.status_code == 200
        business_ids = {c["case_id"] for c in resp.json()}
        assert {"ROLE-ADMIN-A", "ROLE-ADMIN-B"}.issubset(business_ids)

    def test_admin_can_grant_and_revoke_and_view_matrix(self, test_db, test_client) -> None:
        _make_user(test_db, "role_admin_2", role=UserRole.ADMIN)
        officer = _make_user(test_db, "role_admin_2_officer")
        full = _build_full_case(test_db, "ROLE-ADMIN-GRANT")
        headers = _login(test_client, "role_admin_2")

        grant_resp = test_client.post(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer.id}", headers=headers
        )
        assert grant_resp.status_code == 201
        assert grant_resp.json()["status"] == "active"

        matrix_resp = test_client.get("/api/v1/admin/case-access", headers=headers)
        assert matrix_resp.status_code == 200
        matrix = matrix_resp.json()
        officer_row = next(u for u in matrix["users"] if u["user_id"] == officer.id)
        assert officer_row["access_by_case_id"][str(full.case_id)] is True

        revoke_resp = test_client.delete(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer.id}", headers=headers
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["status"] == "revoked"

        matrix_resp_2 = test_client.get("/api/v1/admin/case-access", headers=headers)
        officer_row_2 = next(u for u in matrix_resp_2.json()["users"] if u["user_id"] == officer.id)
        assert officer_row_2["access_by_case_id"][str(full.case_id)] is False

    def test_officer_can_see_assigned_case_only(self, test_db, test_client) -> None:
        admin = _make_user(test_db, "role_admin_3", role=UserRole.ADMIN)
        officer = _make_user(test_db, "role_officer_3")
        assigned = _build_full_case(test_db, "ROLE-OFF-ASSIGNED")
        _build_full_case(test_db, "ROLE-OFF-UNASSIGNED")
        CaseAuthorizationService.grant_case_access(
            test_db, admin, user_id=officer.id, case_id=assigned.case_id
        )
        headers = _login(test_client, "role_officer_3")

        list_resp = test_client.get("/api/v1/cases", headers=headers)
        assert list_resp.status_code == 200
        business_ids = {c["case_id"] for c in list_resp.json()}
        assert business_ids == {"ROLE-OFF-ASSIGNED"}

        get_resp = test_client.get(f"/api/v1/cases/{assigned.case_id}", headers=headers)
        assert get_resp.status_code == 200

    def test_officer_cannot_grant_or_revoke_access(self, test_db, test_client) -> None:
        _make_user(test_db, "role_officer_noadmin")
        target = _make_user(test_db, "role_officer_noadmin_target")
        full = _build_full_case(test_db, "ROLE-OFF-NOADMIN")
        headers = _login(test_client, "role_officer_noadmin")

        grant_resp = test_client.post(
            f"/api/v1/admin/cases/{full.case_id}/access/{target.id}", headers=headers
        )
        assert grant_resp.status_code == 403

        revoke_resp = test_client.delete(
            f"/api/v1/admin/cases/{full.case_id}/access/{target.id}", headers=headers
        )
        assert revoke_resp.status_code == 403

        matrix_resp = test_client.get("/api/v1/admin/case-access", headers=headers)
        assert matrix_resp.status_code == 403

    def test_lab_personnel_access_follows_explicit_policy_and_cannot_escalate(
        self, test_db, test_client
    ) -> None:
        admin = _make_user(test_db, "role_admin_lab", role=UserRole.ADMIN)
        lab = _make_user(test_db, "role_lab_1", role=UserRole.LAB_PERSONNEL)
        full = _build_full_case(test_db, "ROLE-LAB-1")
        headers = _login(test_client, "role_lab_1")

        # No automatic access merely from being authenticated.
        denied = test_client.get(f"/api/v1/cases/{full.case_id}", headers=headers)
        assert denied.status_code == 403

        # Cannot escalate by calling admin endpoints either.
        escalate = test_client.post(
            f"/api/v1/admin/cases/{full.case_id}/access/{lab.id}", headers=headers
        )
        assert escalate.status_code == 403

        CaseAuthorizationService.grant_case_access(
            test_db, admin, user_id=lab.id, case_id=full.case_id
        )
        allowed = test_client.get(f"/api/v1/cases/{full.case_id}", headers=headers)
        assert allowed.status_code == 200


# =============================================================================
# Section 17/18: every case-scoped route type rejects an officer with no
# case assignment; IDOR sweep across two real cases.
# =============================================================================


def _all_case_scoped_route_checks(full: FullCase):
    """`(method, path)` pairs covering every resource category task
    section 5 names explicitly. All are read-only GETs -- deliberately:
    this sweep exists to prove *visibility* is blocked, not to also
    exercise every mutating side effect (those have their own tests)."""
    return [
        ("GET", f"/api/v1/cases/{full.case_id}"),
        ("GET", f"/api/v1/cases/{full.case_id}/evidence"),
        ("GET", f"/api/v1/evidence/{full.evidence_id}"),
        ("GET", f"/api/v1/evidence/{full.evidence_id}/recordings"),
        ("GET", f"/api/v1/recordings/{full.recording_id}"),
        ("GET", f"/api/v1/recordings/{full.recording_id}/metadata"),
        ("GET", f"/api/v1/artifacts/{full.artifact_id}"),
        ("GET", f"/api/v1/artifacts/{full.artifact_id}/download"),
        ("GET", f"/api/v1/evidence/{full.evidence_id}/artifacts"),
        ("GET", f"/api/v1/evidence/{full.evidence_id}/recovery-results"),
        ("GET", f"/api/v1/evidence/{full.evidence_id}/hashes"),
        ("GET", f"/api/v1/cases/{full.case_id}/ai-results"),
        ("GET", f"/api/v1/cases/{full.case_id}/findings"),
        ("GET", f"/api/v1/findings/{full.finding_id}"),
        ("GET", f"/api/v1/cases/{full.case_id}/timeline"),
        ("GET", f"/api/v1/cases/{full.case_id}/correlation/events"),
        ("GET", f"/api/v1/cases/{full.case_id}/validation"),
        ("GET", f"/api/v1/cases/{full.case_id}/reports"),
        ("GET", f"/api/v1/reports/{full.report_id}"),
        ("GET", f"/api/v1/reports/{full.report_id}/download"),
        ("GET", f"/api/v1/cases/{full.case_id}/audit"),
        ("GET", f"/api/v1/evidence/{full.evidence_id}/custody"),
        ("GET", f"/api/v1/cases/{full.case_id}/audit/verify"),
        ("GET", f"/api/v1/cases/{full.case_id}/blockchain/anchors"),
        ("GET", f"/api/v1/cases/{full.case_id}/processing"),
        ("GET", f"/api/v1/jobs/{full.job_id}"),
        ("GET", f"/api/v1/evidence/{full.evidence_id}/custody/history"),
        ("GET", f"/api/v1/evidence/{full.evidence_id}/custody/current"),
    ]


class TestEveryCaseScopedRouteRejectsUnauthorizedOfficer:
    """Task section 17: explicitly test an officer with NO case assignment
    against every case-scoped route category."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db, test_client):
        self.officer = _make_user(test_db, "sweep_officer_no_access")
        self.full = _build_full_case(test_db, "SWEEP-NOACCESS")
        self.headers = _login(test_client, "sweep_officer_no_access")

    def test_all_routes_reject(self, test_client) -> None:
        failures = []
        for method, path in _all_case_scoped_route_checks(self.full):
            resp = test_client.request(method, path, headers=self.headers)
            if resp.status_code != 403:
                failures.append((method, path, resp.status_code))
        assert failures == [], f"expected 403 for every route, got: {failures}"

    def test_unauthenticated_caller_also_rejected(self, test_client) -> None:
        """No header at all -> 401, never a silent 200."""
        for method, path in _all_case_scoped_route_checks(self.full):
            resp = test_client.request(method, path)
            assert resp.status_code in (401, 403), (method, path, resp.status_code)


class TestIDOR:
    """Task section 18: Case A / Case B, officer assigned only to Case A.
    Every attempt to reach Case B's data -- by ID alone, having never been
    granted access -- must fail, across the full route sweep."""

    @pytest.fixture(autouse=True)
    def _setup(self, test_db, test_client):
        admin = _make_user(test_db, "idor_admin", role=UserRole.ADMIN)
        self.officer = _make_user(test_db, "idor_officer")
        self.case_a = _build_full_case(test_db, "IDOR-CASE-A")
        self.case_b = _build_full_case(test_db, "IDOR-CASE-B")
        CaseAuthorizationService.grant_case_access(
            test_db, admin, user_id=self.officer.id, case_id=self.case_a.case_id
        )
        self.headers = _login(test_client, "idor_officer")

    def test_case_a_is_reachable(self, test_client) -> None:
        """Confirms access is granted, not that every route's underlying
        business logic fully succeeds against synthetic fixture data
        (`GET .../recordings`, for instance, genuinely re-parses
        `Evidence.source_path` as a real CP Plus container -- a business-
        logic 400 there is not an authorization failure)."""
        for method, path in _all_case_scoped_route_checks(self.case_a):
            resp = test_client.request(method, path, headers=self.headers)
            assert resp.status_code not in (401, 403), (method, path, resp.status_code, resp.text)

    def test_case_b_is_never_reachable_by_id_alone(self, test_client) -> None:
        failures = []
        for method, path in _all_case_scoped_route_checks(self.case_b):
            resp = test_client.request(method, path, headers=self.headers)
            if resp.status_code != 403:
                failures.append((method, path, resp.status_code))
        assert failures == [], f"Case B leaked through: {failures}"

    def test_case_b_video_search_and_ai_job_creation_also_rejected(self, test_client) -> None:
        """Body-based `case_id` routes (ai.py/validation.py's job creation,
        search.py) authorize manually -- covered separately from the
        generic sweep above since they take `case_id` in the JSON body,
        not the URL."""
        search_resp = test_client.post(
            f"/api/v1/cases/{self.case_b.case_id}/video-search",
            json={"query": "red car"},
            headers=self.headers,
        )
        assert search_resp.status_code == 403

        ai_job_resp = test_client.post(
            "/api/v1/ai/jobs",
            json={
                "case_id": self.case_b.case_id,
                "recording_ids": [self.case_b.recording_id],
                "analysis_types": ["motion_detection"],
            },
            headers=self.headers,
        )
        assert ai_job_resp.status_code == 403

    def test_case_b_processing_and_reports_creation_rejected(self, test_client) -> None:
        process_resp = test_client.post(
            f"/api/v1/cases/{self.case_b.case_id}/process", headers=self.headers
        )
        assert process_resp.status_code == 403

        report_resp = test_client.post(
            f"/api/v1/cases/{self.case_b.case_id}/reports", json={}, headers=self.headers
        )
        assert report_resp.status_code == 403

    def test_changing_case_id_in_url_manually_is_still_rejected(self, test_client) -> None:
        """The literal scenario task section 30's "CRITICAL RULE" names:
        an officer editing `/cases/CASE-002` in the request by hand."""
        resp = test_client.get(f"/api/v1/cases/{self.case_b.case_id}", headers=self.headers)
        assert resp.status_code == 403
        # And the response body never discloses Case B's real content.
        assert "IDOR-CASE-B" not in json.dumps(resp.json())


# =============================================================================
# Section 19: grant -> access begins working; revoke -> access disappears.
# =============================================================================


class TestGrantRevokeFlow:
    def test_grant_then_access_then_revoke_then_no_access(self, test_db, test_client) -> None:
        _make_user(test_db, "flow_admin", role=UserRole.ADMIN)
        officer = _make_user(test_db, "flow_officer")
        full = _build_full_case(test_db, "FLOW-CASE-1")
        admin_headers = _login(test_client, "flow_admin")
        officer_headers = _login(test_client, "flow_officer")

        # Before grant: rejected.
        before = test_client.get(f"/api/v1/cases/{full.case_id}", headers=officer_headers)
        assert before.status_code == 403

        # Grant.
        grant_resp = test_client.post(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer.id}",
            json={"reason": "assigned to investigation"},
            headers=admin_headers,
        )
        assert grant_resp.status_code == 201

        # After grant: works.
        after_grant = test_client.get(f"/api/v1/cases/{full.case_id}", headers=officer_headers)
        assert after_grant.status_code == 200
        evidence_after_grant = test_client.get(
            f"/api/v1/cases/{full.case_id}/evidence", headers=officer_headers
        )
        assert evidence_after_grant.status_code == 200

        # Revoke.
        revoke_resp = test_client.delete(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer.id}", headers=admin_headers
        )
        assert revoke_resp.status_code == 200

        # After revoke: rejected again, including a resource the officer
        # was actively able to read moments before (task section 14,
        # "Case Access Revocation Safety").
        after_revoke = test_client.get(f"/api/v1/cases/{full.case_id}", headers=officer_headers)
        assert after_revoke.status_code == 403
        evidence_after_revoke = test_client.get(
            f"/api/v1/cases/{full.case_id}/evidence", headers=officer_headers
        )
        assert evidence_after_revoke.status_code == 403

    def test_grant_and_revoke_record_audit_events_in_the_hash_chain(
        self, test_db, test_client
    ) -> None:
        """Task section 10/11: grant/revoke must appear in the existing
        audit chain, and the chain must remain verifiable afterward."""
        _make_user(test_db, "audit_flow_admin", role=UserRole.ADMIN)
        officer = _make_user(test_db, "audit_flow_officer")
        full = _build_full_case(test_db, "AUDIT-FLOW-1")
        admin_headers = _login(test_client, "audit_flow_admin")

        test_client.post(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer.id}", headers=admin_headers
        )
        test_client.delete(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer.id}", headers=admin_headers
        )

        audit_resp = test_client.get(f"/api/v1/cases/{full.case_id}/audit", headers=admin_headers)
        assert audit_resp.status_code == 200
        events = audit_resp.json()
        access_events = [e for e in events if e["operation"] == "case_access_change"]
        assert len(access_events) == 2
        actions = {(e["parameters"] or {}).get("action") for e in access_events}
        assert actions == {"grant", "revoke"}
        for event in access_events:
            assert event["previous_hash"] is not None
            assert event["current_hash"] is not None

        verify_resp = test_client.get(
            f"/api/v1/cases/{full.case_id}/audit/verify", headers=admin_headers
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["valid"] is True


# =============================================================================
# Section 20: multiple officers on one case.
# =============================================================================


class TestMultipleOfficers:
    def test_grant_revoke_sequencing_across_two_officers(self, test_db, test_client) -> None:
        _make_user(test_db, "multi_admin", role=UserRole.ADMIN)
        officer_1 = _make_user(test_db, "multi_officer_1")
        officer_2 = _make_user(test_db, "multi_officer_2")
        full = _build_full_case(test_db, "MULTI-CASE-1")
        admin_headers = _login(test_client, "multi_admin")
        headers_1 = _login(test_client, "multi_officer_1")
        headers_2 = _login(test_client, "multi_officer_2")

        # Grant officer 1 only.
        test_client.post(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer_1.id}", headers=admin_headers
        )
        assert (
            test_client.get(f"/api/v1/cases/{full.case_id}", headers=headers_1).status_code == 200
        )
        assert (
            test_client.get(f"/api/v1/cases/{full.case_id}", headers=headers_2).status_code == 403
        )

        # Grant officer 2 too -- both now have access.
        test_client.post(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer_2.id}", headers=admin_headers
        )
        assert (
            test_client.get(f"/api/v1/cases/{full.case_id}", headers=headers_1).status_code == 200
        )
        assert (
            test_client.get(f"/api/v1/cases/{full.case_id}", headers=headers_2).status_code == 200
        )

        # Revoke officer 1 -- only officer 2 remains.
        test_client.delete(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer_1.id}", headers=admin_headers
        )
        assert (
            test_client.get(f"/api/v1/cases/{full.case_id}", headers=headers_1).status_code == 403
        )
        assert (
            test_client.get(f"/api/v1/cases/{full.case_id}", headers=headers_2).status_code == 200
        )

        matrix = test_client.get("/api/v1/admin/case-access", headers=admin_headers).json()
        row_1 = next(u for u in matrix["users"] if u["user_id"] == officer_1.id)
        row_2 = next(u for u in matrix["users"] if u["user_id"] == officer_2.id)
        assert row_1["access_by_case_id"][str(full.case_id)] is False
        assert row_2["access_by_case_id"][str(full.case_id)] is True


# =============================================================================
# Section 25: security -- mass assignment / caller-supplied identity checks.
# =============================================================================


class TestSecurityBoundaries:
    def test_grant_actor_identity_comes_from_session_not_request_body(
        self, test_db, test_client
    ) -> None:
        """`CaseAccessGrantRequest` has no admin-identity field at all --
        confirm the audit trail records the *authenticated* admin, not
        anything a caller could have tried to inject."""
        admin = _make_user(test_db, "sec_admin", role=UserRole.ADMIN)
        officer = _make_user(test_db, "sec_officer")
        full = _build_full_case(test_db, "SEC-CASE-1")
        admin_headers = _login(test_client, "sec_admin")

        resp = test_client.post(
            f"/api/v1/admin/cases/{full.case_id}/access/{officer.id}",
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["granted_by_user_id"] == admin.id
        assert resp.json()["granted_by_display_name"] == admin.display_name

    def test_case_id_manipulation_via_admin_grant_endpoint_requires_real_ids(
        self, test_db, test_client
    ) -> None:
        _make_user(test_db, "sec_admin_2", role=UserRole.ADMIN)
        admin_headers = _login(test_client, "sec_admin_2")
        resp = test_client.post("/api/v1/admin/cases/999999/access/999999", headers=admin_headers)
        assert resp.status_code == 404
