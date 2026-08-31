"""Tests for POST /cases/{case_id}/evidence/upload (Phase 23)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings
from app.core.case_manager import CaseManager
from app.schemas.case import CaseCreateRequest


@pytest.fixture
def evidence_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def test_upload_evidence_registers_and_writes_file(
    test_db, test_client, evidence_root: Path, make_authenticated_headers
) -> None:
    case = CaseManager.create_case(test_db, CaseCreateRequest(case_id="UP-1", name="Upload test"))

    resp = test_client.post(
        f"/api/v1/cases/{case.id}/evidence/upload",
        data={
            "evidence_id": "UP-1-EV1",
            "source_type": "native_export",
            "source_description": "Uploaded via test",
        },
        files={"file": ("clip.cpv", b"fake cpv bytes here", "application/octet-stream")},
        headers=make_authenticated_headers(),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["evidence_id"] == "UP-1-EV1"
    assert body["source_type"] == "native_export"
    assert body["source_path"] is not None
    saved = Path(body["source_path"])
    assert saved.is_file()
    assert saved.read_bytes() == b"fake cpv bytes here"
    assert str(evidence_root.resolve()) in str(saved)


def test_upload_evidence_unknown_case_404(test_client, make_authenticated_headers) -> None:
    resp = test_client.post(
        "/api/v1/cases/999999/evidence/upload",
        data={"evidence_id": "X", "source_type": "native_export"},
        files={"file": ("clip.cpv", b"data", "application/octet-stream")},
        headers=make_authenticated_headers(),
    )
    assert resp.status_code == 404


def test_upload_evidence_duplicate_evidence_id_400(
    test_db, test_client, evidence_root: Path, make_authenticated_headers
) -> None:
    case = CaseManager.create_case(test_db, CaseCreateRequest(case_id="UP-2", name="Upload dup"))
    files = {"file": ("clip.cpv", b"data", "application/octet-stream")}
    data = {"evidence_id": "UP-2-EV1", "source_type": "native_export"}
    headers = make_authenticated_headers()

    first = test_client.post(
        f"/api/v1/cases/{case.id}/evidence/upload", data=data, files=files, headers=headers
    )
    assert first.status_code == 201

    second = test_client.post(
        f"/api/v1/cases/{case.id}/evidence/upload", data=data, files=files, headers=headers
    )
    assert second.status_code == 400


def test_upload_evidence_rejects_path_traversal_filename(
    test_db, test_client, evidence_root: Path, make_authenticated_headers
) -> None:
    case = CaseManager.create_case(
        test_db, CaseCreateRequest(case_id="UP-3", name="Upload traversal")
    )
    resp = test_client.post(
        f"/api/v1/cases/{case.id}/evidence/upload",
        data={"evidence_id": "UP-3-EV1", "source_type": "native_export"},
        files={"file": ("../../etc/passwd", b"data", "application/octet-stream")},
        headers=make_authenticated_headers(),
    )
    assert resp.status_code == 201
    saved = Path(resp.json()["source_path"])
    # The malicious directory components are stripped to a bare filename --
    # the file lands inside EVIDENCE_ROOT, never escaping it.
    assert str(evidence_root.resolve()) in str(saved)
    assert saved.is_file()
