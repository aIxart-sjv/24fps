"""Tests for POST /cases/{case_id}/video-search (Phase 23)."""

from __future__ import annotations

from app.core.case_manager import CaseManager
from app.schemas.case import CaseCreateRequest


def test_video_search_unknown_case_404(test_client, make_authenticated_headers) -> None:
    resp = test_client.post(
        "/api/v1/cases/999999/video-search",
        json={"query": "red shirt"},
        headers=make_authenticated_headers(),
    )
    assert resp.status_code == 404


def test_video_search_unrecognized_query_reports_disclaimer_and_vocabulary(
    test_db, test_client, make_authenticated_headers
) -> None:
    case = CaseManager.create_case(
        test_db, CaseCreateRequest(case_id="VS-1", name="Search API test")
    )

    resp = test_client.post(
        f"/api/v1/cases/{case.id}/video-search",
        json={"query": "someone suspicious"},
        headers=make_authenticated_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recognized"] is False
    assert body["sightings"] == []
    assert "red" in body["supported_colors"]
    assert "identity" in body["disclaimer"].lower()


def test_video_search_with_no_detections_returns_empty_and_honest_warning(
    test_db, test_client, make_authenticated_headers
) -> None:
    case = CaseManager.create_case(
        test_db, CaseCreateRequest(case_id="VS-2", name="Search API test 2")
    )

    resp = test_client.post(
        f"/api/v1/cases/{case.id}/video-search",
        json={"query": "red shirt guy"},
        headers=make_authenticated_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recognized"] is True
    assert body["sightings"] == []
    assert body["warnings"]
