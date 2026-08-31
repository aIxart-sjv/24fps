"""HTTP-level tests for app/api/routes/{processing,findings,notifications}.py
(Phase 22). Uses the shared `test_db`/`test_client` fixtures together,
matching tests/test_custody_api.py's own established pattern.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.core.auth_manager import AuthManager
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.models import UserRole
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest


def _make_case(db, case_id: str = "CASE-PROC-API-1"):
    return CaseManager.create_case(
        db, CaseCreateRequest(case_id=case_id, name="Processing API test")
    )


def _make_user(db, username: str, password: str = "password123", role: UserRole = UserRole.OFFICER):
    return AuthManager.create_user(
        db, username=username, display_name=username.title(), password=password, role=role
    )


def _auth_headers(test_client, username: str, password: str = "password123") -> dict[str, str]:
    resp = test_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _register_native_export_evidence(db, case, tmp_path: Path, content: bytes):
    monkey_evidence_root = tmp_path / "evidence"
    monkey_evidence_root.mkdir(exist_ok=True)
    path = monkey_evidence_root / "garbage.cpv"
    path.write_bytes(content)
    return EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id="EV-GARBAGE", source_type="native_export", source_path=str(path)
        ),
    )


class TestProcessingApi:
    def test_process_case_requires_authentication(self, test_db, test_client) -> None:
        case = _make_case(test_db)
        resp = test_client.post(f"/api/v1/cases/{case.id}/process")
        assert resp.status_code == 401

    def test_process_case_unknown_case_404(
        self, test_db, test_client, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setenv("EVIDENCE_ROOT", str(tmp_path))
        get_settings.cache_clear()
        _make_user(test_db, "officer_404")
        headers = _auth_headers(test_client, "officer_404")
        resp = test_client.post("/api/v1/cases/999999/process", headers=headers)
        assert resp.status_code == 404
        get_settings.cache_clear()

    def test_process_case_generates_findings_and_notifications(
        self, test_db, test_client, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setenv("EVIDENCE_ROOT", str(tmp_path / "evidence"))
        monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
        get_settings.cache_clear()
        case = _make_case(test_db)
        _register_native_export_evidence(
            test_db, case, tmp_path, b"not a real cpv file, no ADIT magic header at all"
        )
        _make_user(test_db, "officer_process", role=UserRole.ADMIN)
        headers = _auth_headers(test_client, "officer_process")

        resp = test_client.post(f"/api/v1/cases/{case.id}/process", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["root_job"]["job_type"] == "orchestration"
        assert body["stages_total"] > 0
        assert body["new_finding_ids"]
        assert body["notification_ids"]

        findings_resp = test_client.get(f"/api/v1/cases/{case.id}/findings", headers=headers)
        assert findings_resp.status_code == 200
        findings = findings_resp.json()
        assert any(f["finding_type"] == "unsupported_format" for f in findings)

        notif_resp = test_client.get("/api/v1/notifications", headers=headers)
        assert notif_resp.status_code == 200
        notifications = notif_resp.json()
        assert len(notifications) == len(body["notification_ids"])
        assert all(n["read_at"] is None for n in notifications)

        first_id = notifications[0]["id"]
        patch_resp = test_client.patch(
            f"/api/v1/notifications/{first_id}", headers=headers, json={"read": True}
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["read_at"] is not None

        unread_resp = test_client.get(
            "/api/v1/notifications", headers=headers, params={"unread_only": True}
        )
        assert all(n["id"] != first_id for n in unread_resp.json())
        get_settings.cache_clear()

    def test_notifications_scoped_to_authenticated_user(
        self, test_db, test_client, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setenv("EVIDENCE_ROOT", str(tmp_path / "evidence"))
        monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
        get_settings.cache_clear()
        case = _make_case(test_db)
        _register_native_export_evidence(test_db, case, tmp_path, b"garbage, no magic header")
        _make_user(test_db, "officer_a", role=UserRole.ADMIN)
        _make_user(test_db, "officer_b")
        headers_a = _auth_headers(test_client, "officer_a")
        headers_b = _auth_headers(test_client, "officer_b")

        process_resp = test_client.post(f"/api/v1/cases/{case.id}/process", headers=headers_a)
        assert process_resp.status_code == 200

        notif_a = test_client.get("/api/v1/notifications", headers=headers_a).json()
        notif_b = test_client.get("/api/v1/notifications", headers=headers_b).json()
        assert len(notif_a) > 0
        assert notif_b == []

        # officer_b cannot see or mutate officer_a's notification.
        other_id = notif_a[0]["id"]
        resp = test_client.patch(
            f"/api/v1/notifications/{other_id}", headers=headers_b, json={"read": True}
        )
        assert resp.status_code == 404
        get_settings.cache_clear()

    def test_finding_lifecycle_update(self, test_db, test_client, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("EVIDENCE_ROOT", str(tmp_path / "evidence"))
        monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
        get_settings.cache_clear()
        case = _make_case(test_db)
        _register_native_export_evidence(test_db, case, tmp_path, b"garbage, no magic header")
        _make_user(test_db, "officer_review", role=UserRole.ADMIN)
        headers = _auth_headers(test_client, "officer_review")
        test_client.post(f"/api/v1/cases/{case.id}/process", headers=headers)

        findings = test_client.get(f"/api/v1/cases/{case.id}/findings", headers=headers).json()
        finding_id = findings[0]["id"]

        resp = test_client.patch(
            f"/api/v1/findings/{finding_id}",
            headers=headers,
            json={"status": "resolved", "resolution_notes": "Reviewed, no action needed."},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "resolved"
        assert body["resolved_at"] is not None
        assert body["resolved_by"] == "Officer_Review"
        get_settings.cache_clear()

    def test_processing_run_lookup_endpoints(
        self, test_db, test_client, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.setenv("EVIDENCE_ROOT", str(tmp_path / "evidence"))
        monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
        get_settings.cache_clear()
        case = _make_case(test_db)
        _register_native_export_evidence(test_db, case, tmp_path, b"garbage, no magic header")
        _make_user(test_db, "officer_lookup", role=UserRole.ADMIN)
        headers = _auth_headers(test_client, "officer_lookup")
        process_resp = test_client.post(f"/api/v1/cases/{case.id}/process", headers=headers)
        root_job_id = process_resp.json()["root_job"]["id"]

        list_resp = test_client.get(f"/api/v1/cases/{case.id}/processing", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        get_resp = test_client.get(f"/api/v1/processing/{root_job_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["root_job"]["id"] == root_job_id

        missing_resp = test_client.get("/api/v1/processing/999999", headers=headers)
        assert missing_resp.status_code == 404
        get_settings.cache_clear()

    def test_processing_run_duration_and_results_endpoint(
        self, test_db, test_client, monkeypatch, tmp_path
    ) -> None:
        """Phase 24-2 task scope, "Processing Performance, Accuracy/
        Validation, and Output Parameter tables from REAL runtime data":
        every stage and the root run must report a real, high-resolution
        measured duration plus real CPU/RSS/input data, and two separate
        endpoints must expose accuracy/validation signals and raw outputs
        -- never mixed together, and never with a timing value leaking
        into either."""
        monkeypatch.setenv("EVIDENCE_ROOT", str(tmp_path / "evidence"))
        monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
        get_settings.cache_clear()
        case = _make_case(test_db)
        _register_native_export_evidence(test_db, case, tmp_path, b"garbage, no magic header")
        _make_user(test_db, "officer_perf", role=UserRole.ADMIN)
        headers = _auth_headers(test_client, "officer_perf")

        process_resp = test_client.post(f"/api/v1/cases/{case.id}/process", headers=headers)
        assert process_resp.status_code == 200, process_resp.text
        body = process_resp.json()
        root_job_id = body["root_job"]["id"]

        assert body["total_duration_seconds"] is not None
        assert body["total_duration_seconds"] >= 0
        assert body["stages"], "expected at least one pipeline stage"
        for stage in body["stages"]:
            assert stage["duration_seconds"] is not None
            assert stage["duration_seconds"] >= 0
            assert stage["high_resolution_timing"] is True
            assert stage["cpu_user_seconds"] is not None
            assert stage["cpu_system_seconds"] is not None
            assert stage["peak_rss_kb"] is not None
            assert stage["peak_rss_kb"] > 0

        # The integrity/identification/enumeration stages all read the
        # same real evidence source file on disk.
        integrity_stage = next(s for s in body["stages"] if s["job_type"] == "integrity")
        assert integrity_stage["input_type"] == "evidence_source_file"
        assert integrity_stage["input_size_unit"] == "bytes"
        assert integrity_stage["input_size"] == len(b"garbage, no magic header")

        accuracy_resp = test_client.get(
            f"/api/v1/processing/{root_job_id}/accuracy", headers=headers
        )
        assert accuracy_resp.status_code == 200, accuracy_resp.text
        accuracy_body = accuracy_resp.json()
        assert accuracy_body["root_job_id"] == root_job_id
        for metric in accuracy_body["metrics"]:
            assert metric["status"] in (
                "VALIDATED",
                "CONTROLLED",
                "OBSERVATION",
                "UNVERIFIED",
                "N/A",
            )
            assert "duration" not in metric["metric"].lower()

        outputs_resp = test_client.get(f"/api/v1/processing/{root_job_id}/outputs", headers=headers)
        assert outputs_resp.status_code == 200, outputs_resp.text
        outputs_body = outputs_resp.json()
        assert outputs_body["root_job_id"] == root_job_id
        assert outputs_body["parameters"]
        output_modules = {p["module"] for p in outputs_body["parameters"]}
        assert "Integrity verification" in output_modules
        # Case-level outputs (never tied to one stage job) are present too.
        assert "Audit chain" in output_modules
        assert "Blockchain" in output_modules
        assert "Report" in output_modules
        for parameter in outputs_body["parameters"]:
            assert "duration" not in parameter["parameter"].lower()

        missing_accuracy_resp = test_client.get(
            "/api/v1/processing/999999/accuracy", headers=headers
        )
        assert missing_accuracy_resp.status_code == 404
        missing_outputs_resp = test_client.get("/api/v1/processing/999999/outputs", headers=headers)
        assert missing_outputs_resp.status_code == 404
        get_settings.cache_clear()
