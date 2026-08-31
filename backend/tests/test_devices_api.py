"""API tests for the Phase 6 identification routes (app/api/routes/devices.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings
from app.models import Case, CaseStatus, Evidence


@pytest.fixture
def evidence_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.fixture
def raw_dd_evidence(test_db, evidence_root: Path) -> Evidence:
    case = Case(case_id="API-ID-CASE-001", name="API Identification Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    image_path = evidence_root / "image.dd"
    image_path.write_bytes(b"\x00" * 4096)

    evidence = Evidence(
        evidence_id="API-ID-E001",
        case_id=case.id,
        source_type="raw_dd",
        source_path=str(image_path.resolve()),
    )
    test_db.add(evidence)
    test_db.commit()
    return evidence


def test_identify_device_endpoint_returns_result(
    test_client, test_db, raw_dd_evidence: Evidence, make_authenticated_headers
):
    headers = make_authenticated_headers()
    response = test_client.post(
        f"/api/v1/evidence/{raw_dd_evidence.id}/identify-device", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "partial"
    assert data["storage_format"] == "raw_dd"
    assert data["device_type"] == "storage_media"
    assert data["vendor"] is None


def test_identify_device_endpoint_not_found(test_client, make_authenticated_headers):
    headers = make_authenticated_headers()
    response = test_client.post("/api/v1/evidence/99999/identify-device", headers=headers)
    # Case-access resolution (Phase 25) now 404s on a nonexistent evidence
    # item before the route body ever runs -- more consistent with every
    # other "not found" response in this codebase than the 400 this used
    # to return.
    assert response.status_code == 404


def test_get_device_before_identification_is_404(
    test_client, test_db, raw_dd_evidence: Evidence, make_authenticated_headers
):
    headers = make_authenticated_headers()
    response = test_client.get(f"/api/v1/evidence/{raw_dd_evidence.id}/device", headers=headers)
    assert response.status_code == 404


def test_get_device_after_identification_returns_persisted_row(
    test_client, test_db, raw_dd_evidence: Evidence, make_authenticated_headers
):
    headers = make_authenticated_headers()
    test_client.post(f"/api/v1/evidence/{raw_dd_evidence.id}/identify-device", headers=headers)

    response = test_client.get(f"/api/v1/evidence/{raw_dd_evidence.id}/device", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_id"] == raw_dd_evidence.id
    assert data["device_type"] == "storage_media"


def test_detect_format_endpoint_returns_result(
    test_client, test_db, raw_dd_evidence: Evidence, make_authenticated_headers
):
    headers = make_authenticated_headers()
    response = test_client.post(
        f"/api/v1/evidence/{raw_dd_evidence.id}/detect-format", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["storage_format"] == "raw_dd"
    assert data["capacity"] == 4096


def test_detect_format_endpoint_not_found(test_client, make_authenticated_headers):
    headers = make_authenticated_headers()
    response = test_client.post("/api/v1/evidence/99999/detect-format", headers=headers)
    assert response.status_code == 404


def test_identify_device_endpoint_is_idempotent(
    test_client, test_db, raw_dd_evidence: Evidence, make_authenticated_headers
):
    headers = make_authenticated_headers()
    first = test_client.post(
        f"/api/v1/evidence/{raw_dd_evidence.id}/identify-device", headers=headers
    )
    second = test_client.post(
        f"/api/v1/evidence/{raw_dd_evidence.id}/identify-device", headers=headers
    )
    assert first.status_code == 200
    assert second.status_code == 200

    get_response = test_client.get(f"/api/v1/evidence/{raw_dd_evidence.id}/device", headers=headers)
    assert get_response.status_code == 200
