"""API tests for the Phase 14 validation routes:
`POST /api/v1/validation/jobs`, `GET /api/v1/cases/{case_id}/validation`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.ai.types import BoundingBox
from app.core.case_manager import CaseManager
from app.core.validation_manager import ValidationManager
from app.models import AIResult, Artifact, Case, Evidence, Recording
from app.schemas.case import CaseCreateRequest

_T0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)


def _make_case(test_db, case_id: str = "API-VAL-CASE-1") -> Case:
    return CaseManager.create_case(
        test_db, CaseCreateRequest(case_id=case_id, name="API validation case")
    )


def _make_recording(test_db, case: Case) -> tuple[Recording, Artifact]:
    evidence = Evidence(evidence_id=f"EVID-{case.case_id}", case_id=case.id, source_type="cp_plus")
    test_db.add(evidence)
    test_db.commit()
    test_db.refresh(evidence)
    artifact = Artifact(
        evidence_id=evidence.id, artifact_type="cp_plus_h264_preview_mp4", path="/x"
    )
    test_db.add(artifact)
    test_db.commit()
    test_db.refresh(artifact)
    recording = Recording(evidence_id=evidence.id, recording_id="REC-API-1", start_normalized=_T0)
    test_db.add(recording)
    test_db.commit()
    test_db.refresh(recording)
    return recording, artifact


def test_create_validation_job_endpoint_runs_object_detection(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    recording, artifact = _make_recording(test_db, case)
    ValidationManager.create_ground_truth(
        test_db,
        case_id=case.id,
        dataset_id="DS-API-OBJ",
        event_type="object_detection",
        recording_id=recording.id,
        object_class="person",
        frame_number=0,
        bbox=BoundingBox(0, 0, 10, 10),
        source_reference="controlled test",
    )
    prediction = AIResult(
        case_id=case.id,
        recording_id=recording.id,
        analysis_type="object_detection",
        model_name="yolov8n.pt",
        model_version="yolov8n",
        frame_number=0,
        class_name="person",
        confidence=0.9,
        bbox_x_min=1,
        bbox_y_min=1,
        bbox_x_max=11,
        bbox_y_max=11,
        source_artifact=artifact.id,
    )
    test_db.add(prediction)
    test_db.commit()

    response = test_client.post(
        "/api/v1/validation/jobs",
        json={
            "case_id": case.id,
            "validation_type": "object_detection",
            "dataset_id": "DS-API-OBJ",
        },
        headers=make_authenticated_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job"]["status"] == "completed"
    assert data["job"]["job_type"] == "validation"
    metric_names = {m["metric_name"] for m in data["metrics"]}
    assert "object_detection.true_positives" in metric_names
    assert "object_detection.precision" in metric_names


def test_create_validation_job_endpoint_missing_case_returns_404(
    test_client, make_authenticated_headers
) -> None:
    response = test_client.post(
        "/api/v1/validation/jobs",
        json={"case_id": 999999, "validation_type": "object_detection", "dataset_id": "x"},
        headers=make_authenticated_headers(),
    )
    assert response.status_code == 404


def test_create_validation_job_endpoint_invalid_type_returns_400(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    response = test_client.post(
        "/api/v1/validation/jobs",
        json={"case_id": case.id, "validation_type": "not_a_real_type", "dataset_id": "x"},
        headers=make_authenticated_headers(),
    )
    assert response.status_code == 400


def test_list_case_validation_endpoint_returns_persisted_metrics(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    recording, _ = _make_recording(test_db, case)
    ValidationManager.create_ground_truth(
        test_db,
        case_id=case.id,
        dataset_id="DS-API-TL",
        event_type="timeline",
        recording_id=recording.id,
        timestamp=_T0,
        source_reference="controlled test",
    )
    headers = make_authenticated_headers()
    test_client.post(
        "/api/v1/validation/jobs",
        json={"case_id": case.id, "validation_type": "timeline", "dataset_id": "DS-API-TL"},
        headers=headers,
    )

    response = test_client.get(f"/api/v1/cases/{case.id}/validation", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(m["validation_type"] == "timeline" for m in data)


def test_list_case_validation_endpoint_filters_by_validation_type(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    recording, _ = _make_recording(test_db, case)
    ValidationManager.create_ground_truth(
        test_db,
        case_id=case.id,
        dataset_id="DS-API-TL2",
        event_type="timeline",
        recording_id=recording.id,
        timestamp=_T0,
        source_reference="controlled test",
    )
    headers = make_authenticated_headers()
    test_client.post(
        "/api/v1/validation/jobs",
        json={"case_id": case.id, "validation_type": "timeline", "dataset_id": "DS-API-TL2"},
        headers=headers,
    )

    matching = test_client.get(
        f"/api/v1/cases/{case.id}/validation",
        params={"validation_type": "timeline"},
        headers=headers,
    )
    non_matching = test_client.get(
        f"/api/v1/cases/{case.id}/validation",
        params={"validation_type": "recovery"},
        headers=headers,
    )

    assert len(matching.json()) > 0
    assert non_matching.json() == []


def test_list_case_validation_endpoint_missing_case_returns_404(
    test_client, make_authenticated_headers
) -> None:
    response = test_client.get(
        "/api/v1/cases/999999/validation", headers=make_authenticated_headers()
    )
    assert response.status_code == 404
