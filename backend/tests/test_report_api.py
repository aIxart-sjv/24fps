"""API tests for the Phase 18 report routes:
`POST /api/v1/cases/{case_id}/reports`, `GET /api/v1/reports/{report_id}`,
`GET /api/v1/reports/{report_id}/download`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings
from app.hashing.sha256 import sha256_bytes
from tests.fixtures.report_case import build_rich_case


@pytest.fixture(autouse=True)
def _report_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("EVIDENCE_ROOT", str(tmp_path / "evidence"))
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("REPORT_ROOT", str(tmp_path / "reports"))
    (tmp_path / "evidence").mkdir()
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "reports").mkdir()
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_create_reports_endpoint_default_both_formats(
    test_client, test_db, make_authenticated_headers
) -> None:
    rich = build_rich_case(test_db)
    response = test_client.post(
        f"/api/v1/cases/{rich.case.id}/reports", json={}, headers=make_authenticated_headers()
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {d["report_type"] for d in data} == {"json", "pdf"}
    for entry in data:
        assert entry["status"] == "completed"
        assert entry["report_hash"] is not None
        assert "path" not in entry  # never exposes a machine-local filesystem path


def test_create_reports_endpoint_single_format(
    test_client, test_db, make_authenticated_headers
) -> None:
    rich = build_rich_case(test_db)
    response = test_client.post(
        f"/api/v1/cases/{rich.case.id}/reports",
        json={"formats": ["json"]},
        headers=make_authenticated_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["report_type"] == "json"


def test_list_case_reports_endpoint(test_client, test_db, make_authenticated_headers) -> None:
    rich = build_rich_case(test_db)
    headers = make_authenticated_headers()
    test_client.post(
        f"/api/v1/cases/{rich.case.id}/reports", json={"formats": ["json"]}, headers=headers
    )
    test_client.post(
        f"/api/v1/cases/{rich.case.id}/reports", json={"formats": ["pdf"]}, headers=headers
    )

    response = test_client.get(f"/api/v1/cases/{rich.case.id}/reports", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {d["report_type"] for d in data} == {"json", "pdf"}


def test_list_case_reports_unknown_case_404(test_client, make_authenticated_headers) -> None:
    response = test_client.get("/api/v1/cases/999999/reports", headers=make_authenticated_headers())
    assert response.status_code == 404


def test_create_reports_missing_case_returns_404(test_client, make_authenticated_headers) -> None:
    response = test_client.post(
        "/api/v1/cases/999999/reports", json={}, headers=make_authenticated_headers()
    )
    assert response.status_code == 404


def test_create_reports_unsupported_format_returns_400(
    test_client, test_db, make_authenticated_headers
) -> None:
    rich = build_rich_case(test_db)
    response = test_client.post(
        f"/api/v1/cases/{rich.case.id}/reports",
        json={"formats": ["csv"]},
        headers=make_authenticated_headers(),
    )
    assert response.status_code == 400


def test_get_report_endpoint(test_client, test_db, make_authenticated_headers) -> None:
    rich = build_rich_case(test_db)
    headers = make_authenticated_headers()
    create_response = test_client.post(
        f"/api/v1/cases/{rich.case.id}/reports", json={"formats": ["json"]}, headers=headers
    )
    report_id = create_response.json()[0]["id"]

    response = test_client.get(f"/api/v1/reports/{report_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == report_id
    assert response.json()["case_id"] == rich.case.id


def test_get_report_missing_returns_404(test_client, make_authenticated_headers) -> None:
    response = test_client.get("/api/v1/reports/999999", headers=make_authenticated_headers())
    assert response.status_code == 404


def test_download_json_report(test_client, test_db, make_authenticated_headers) -> None:
    rich = build_rich_case(test_db)
    headers = make_authenticated_headers()
    create_response = test_client.post(
        f"/api/v1/cases/{rich.case.id}/reports", json={"formats": ["json"]}, headers=headers
    )
    report = create_response.json()[0]

    response = test_client.get(f"/api/v1/reports/{report['id']}/download", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert sha256_bytes(response.content) == report["report_hash"]

    import json as json_module

    parsed = json_module.loads(response.content)
    assert parsed["case"]["case_identifier"] == rich.case.case_id


def test_download_pdf_report(test_client, test_db, make_authenticated_headers) -> None:
    rich = build_rich_case(test_db)
    headers = make_authenticated_headers()
    create_response = test_client.post(
        f"/api/v1/cases/{rich.case.id}/reports", json={"formats": ["pdf"]}, headers=headers
    )
    report = create_response.json()[0]

    response = test_client.get(f"/api/v1/reports/{report['id']}/download", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert sha256_bytes(response.content) == report["report_hash"]


def test_download_report_missing_returns_404(test_client, make_authenticated_headers) -> None:
    response = test_client.get(
        "/api/v1/reports/999999/download", headers=make_authenticated_headers()
    )
    assert response.status_code == 404


def test_report_response_never_includes_blockchain_or_report_body_fields(
    test_client, test_db, make_authenticated_headers
) -> None:
    """The metadata response is not the report body itself -- confirm it
    stays a lightweight envelope, never the full assembled content."""
    rich = build_rich_case(test_db)
    response = test_client.post(
        f"/api/v1/cases/{rich.case.id}/reports",
        json={"formats": ["json"]},
        headers=make_authenticated_headers(),
    )
    entry = response.json()[0]
    assert "evidence" not in entry
    assert "limitations" not in entry
