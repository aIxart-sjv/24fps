"""Tests for app/api/routes/acquisition.py (Phase 23)."""

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
    case = Case(case_id="ACQ-API-001", name="Acquisition API Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    image_path = evidence_root / "image.dd"
    image_path.write_bytes(b"\xaa\xbb\xcc\xdd" * 256)

    evidence = Evidence(
        evidence_id="ACQ-API-E001",
        case_id=case.id,
        source_type="raw_dd",
        source_path=str(image_path.resolve()),
    )
    test_db.add(evidence)
    test_db.commit()
    test_db.refresh(evidence)
    return evidence


def test_get_manifest_before_capture_404(
    test_client, raw_dd_evidence: Evidence, make_authenticated_headers
) -> None:
    resp = test_client.get(
        f"/api/v1/evidence/{raw_dd_evidence.id}/acquisition-manifest",
        headers=make_authenticated_headers(),
    )
    assert resp.status_code == 404


def test_capture_and_read_acquisition_manifest(
    test_client, raw_dd_evidence: Evidence, make_authenticated_headers
) -> None:
    headers = make_authenticated_headers()
    post_resp = test_client.post(
        f"/api/v1/evidence/{raw_dd_evidence.id}/acquisition-manifest", headers=headers
    )
    assert post_resp.status_code == 201
    body = post_resp.json()
    assert body["artifact_type"] == "acquisition_manifest"

    get_resp = test_client.get(
        f"/api/v1/evidence/{raw_dd_evidence.id}/acquisition-manifest", headers=headers
    )
    assert get_resp.status_code == 200
    manifest = get_resp.json()
    assert manifest["evidence_id"] == "ACQ-API-E001"
    assert manifest["source_type"] == "raw_dd"


def test_capture_manifest_unknown_evidence_400(test_client, make_authenticated_headers) -> None:
    resp = test_client.post(
        "/api/v1/evidence/999999/acquisition-manifest", headers=make_authenticated_headers()
    )
    # Case-access resolution (Phase 25) now 404s a nonexistent evidence
    # item before the route body runs, unlike the 400 this used to return.
    assert resp.status_code == 404
