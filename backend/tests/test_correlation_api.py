"""API tests for the Phase 12 correlation routes (app/api/routes/correlation.py):
`POST /api/v1/cases/{case_id}/correlation/run`,
`GET /api/v1/cases/{case_id}/correlation/events`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.case_manager import CaseManager
from app.core.timeline_manager import TimelineManager
from app.models import Case
from app.schemas.case import CaseCreateRequest


def _make_case(test_db, case_id: str = "API-CORR-CASE-1") -> Case:
    return CaseManager.create_case(test_db, CaseCreateRequest(case_id=case_id, name="API case"))


def _marker(test_db, case: Case, camera_id: str, timestamp: datetime) -> None:
    TimelineManager.create_examiner_marker(
        test_db,
        case_id=case.id,
        camera_id=camera_id,
        recording_id=None,
        timestamp=timestamp,
        description=f"event on {camera_id}",
    )


def test_run_correlation_endpoint_reproduces_the_a_b_c_scenario(test_client, test_db) -> None:
    case = _make_case(test_db)
    _marker(test_db, case, "A", datetime(2026, 8, 30, 10, 0, 12, tzinfo=UTC))
    _marker(test_db, case, "B", datetime(2026, 8, 30, 10, 0, 19, tzinfo=UTC))
    _marker(test_db, case, "C", datetime(2026, 8, 30, 10, 0, 31, tzinfo=UTC))

    response = test_client.post(
        f"/api/v1/cases/{case.id}/correlation/run",
        json={
            "topology": [
                {"from_camera_id": "A", "to_camera_id": "B"},
                {"from_camera_id": "B", "to_camera_id": "C"},
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case.id
    assert len(data["candidates"]) == 1
    candidate = data["candidates"][0]
    assert len(candidate["event_ids"]) == 3
    assert candidate["status"] == "correlated_candidate"

    # No response text anywhere claims identity confirmation.
    blob = str(data).lower()
    for forbidden in ("same person", "identity", "confirmed"):
        assert forbidden not in blob


def test_run_correlation_endpoint_without_topology_reports_it_unavailable(
    test_client, test_db
) -> None:
    case = _make_case(test_db)
    _marker(test_db, case, "A", datetime(2026, 8, 30, 10, 0, 12, tzinfo=UTC))
    _marker(test_db, case, "B", datetime(2026, 8, 30, 10, 0, 19, tzinfo=UTC))

    response = test_client.post(f"/api/v1/cases/{case.id}/correlation/run", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["topology_configured"] is False


def test_run_correlation_endpoint_outside_window_yields_no_candidates(test_client, test_db) -> None:
    case = _make_case(test_db)
    _marker(test_db, case, "A", datetime(2026, 8, 30, 10, 0, 12, tzinfo=UTC))
    _marker(test_db, case, "D", datetime(2026, 8, 30, 10, 10, 0, tzinfo=UTC))

    response = test_client.post(f"/api/v1/cases/{case.id}/correlation/run", json={})

    assert response.status_code == 200
    assert response.json()["candidates"] == []


def test_run_correlation_endpoint_missing_case_returns_404(test_client) -> None:
    response = test_client.post("/api/v1/cases/999999/correlation/run", json={})
    assert response.status_code == 404


def test_list_correlation_events_endpoint_returns_persisted_candidates(
    test_client, test_db
) -> None:
    case = _make_case(test_db)
    _marker(test_db, case, "A", datetime(2026, 8, 30, 10, 0, 12, tzinfo=UTC))
    _marker(test_db, case, "B", datetime(2026, 8, 30, 10, 0, 19, tzinfo=UTC))
    test_client.post(
        f"/api/v1/cases/{case.id}/correlation/run",
        json={"topology": [{"from_camera_id": "A", "to_camera_id": "B"}]},
    )

    response = test_client.get(f"/api/v1/cases/{case.id}/correlation/events")

    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["event_ids"]


def test_list_correlation_events_endpoint_missing_case_returns_404(test_client) -> None:
    response = test_client.get("/api/v1/cases/999999/correlation/events")
    assert response.status_code == 404
