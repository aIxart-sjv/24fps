"""API tests for the Phase 13 AI/job routes:
`POST /api/v1/ai/jobs`, `GET /api/v1/jobs/{job_id}`,
`GET /api/v1/cases/{case_id}/ai-results`.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.core.case_manager import CaseManager
from app.models import AIResult, Artifact, Case, Evidence, Recording
from app.schemas.case import CaseCreateRequest
from tests.fixtures.ai_models import requires_object_detection_model


def _make_case(test_db, case_id: str = "API-AI-CASE-1") -> Case:
    return CaseManager.create_case(test_db, CaseCreateRequest(case_id=case_id, name="API AI case"))


def _make_recording_with_clip(test_db, case: Case, tmp_path: Path) -> Recording:
    evidence = Evidence(evidence_id=f"EVID-{case.case_id}", case_id=case.id, source_type="cp_plus")
    test_db.add(evidence)
    test_db.commit()
    test_db.refresh(evidence)

    clip_path = tmp_path / "clip.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(clip_path), fourcc, 5.0, (160, 120))
    for i in range(10):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        x = 10 + (i * 10) % 100
        frame[20:60, x : x + 30] = 255
        writer.write(frame)
    writer.release()

    artifact = Artifact(
        evidence_id=evidence.id,
        artifact_type="cp_plus_h264_preview_mp4",
        path=str(clip_path),
        size_bytes=clip_path.stat().st_size,
    )
    test_db.add(artifact)
    test_db.commit()
    test_db.refresh(artifact)

    recording = Recording(
        evidence_id=evidence.id, recording_id="REC-API-1", artifact_id=str(artifact.id)
    )
    test_db.add(recording)
    test_db.commit()
    test_db.refresh(recording)
    return recording


def test_create_ai_job_endpoint_runs_motion_detection(
    test_client, test_db, tmp_path: Path, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    recording = _make_recording_with_clip(test_db, case, tmp_path)

    response = test_client.post(
        "/api/v1/ai/jobs",
        json={
            "case_id": case.id,
            "recording_ids": [recording.id],
            "analysis_types": ["motion_detection"],
            "sampling_strategy": "all",
        },
        headers=make_authenticated_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["job_type"] == "ai"
    assert data["case_id"] == case.id
    assert data["recording_ids"] == [recording.id]
    assert data["worker"] in ("cpu", "cuda:0")
    assert data["completed_at"] is not None


def test_create_ai_job_endpoint_missing_case_returns_404(
    test_client, make_authenticated_headers
) -> None:
    response = test_client.post(
        "/api/v1/ai/jobs",
        json={
            "case_id": 999999,
            "recording_ids": [1],
            "analysis_types": ["motion_detection"],
        },
        headers=make_authenticated_headers(),
    )

    assert response.status_code == 404


def test_create_ai_job_endpoint_invalid_analysis_type_returns_400(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)

    response = test_client.post(
        "/api/v1/ai/jobs",
        json={"case_id": case.id, "recording_ids": [1], "analysis_types": ["not_a_real_type"]},
        headers=make_authenticated_headers(),
    )

    assert response.status_code == 400


def test_get_job_endpoint_returns_the_job(
    test_client, test_db, tmp_path: Path, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    recording = _make_recording_with_clip(test_db, case, tmp_path)
    headers = make_authenticated_headers()

    created = test_client.post(
        "/api/v1/ai/jobs",
        json={
            "case_id": case.id,
            "recording_ids": [recording.id],
            "analysis_types": ["motion_detection"],
            "sampling_strategy": "all",
        },
        headers=headers,
    ).json()

    response = test_client.get(f"/api/v1/jobs/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["status"] == "completed"


def test_get_job_endpoint_missing_job_returns_404(test_client, make_authenticated_headers) -> None:
    response = test_client.get("/api/v1/jobs/999999", headers=make_authenticated_headers())
    assert response.status_code == 404


def test_list_ai_results_endpoint_returns_persisted_results(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    evidence = Evidence(evidence_id="EVID-LISTAI", case_id=case.id, source_type="cp_plus")
    test_db.add(evidence)
    test_db.commit()
    test_db.refresh(evidence)
    artifact = Artifact(
        evidence_id=evidence.id, artifact_type="cp_plus_h264_preview_mp4", path="/x"
    )
    test_db.add(artifact)
    test_db.commit()
    test_db.refresh(artifact)
    recording = Recording(evidence_id=evidence.id, recording_id="REC-LISTAI")
    test_db.add(recording)
    test_db.commit()
    test_db.refresh(recording)
    result = AIResult(
        case_id=case.id,
        recording_id=recording.id,
        analysis_type="object_detection",
        model_name="yolov8n.pt",
        model_version="yolov8n",
        frame_number=0,
        class_name="person",
        confidence=0.9,
        bbox_x_min=0.0,
        bbox_y_min=0.0,
        bbox_x_max=10.0,
        bbox_y_max=10.0,
        source_artifact=artifact.id,
    )
    test_db.add(result)
    test_db.commit()

    response = test_client.get(
        f"/api/v1/cases/{case.id}/ai-results", headers=make_authenticated_headers()
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["class_name"] == "person"
    assert data[0]["bbox"] == {"x_min": 0.0, "y_min": 0.0, "x_max": 10.0, "y_max": 10.0}


def test_list_ai_results_endpoint_missing_case_returns_404(
    test_client, make_authenticated_headers
) -> None:
    response = test_client.get(
        "/api/v1/cases/999999/ai-results", headers=make_authenticated_headers()
    )
    assert response.status_code == 404


@requires_object_detection_model
def test_real_ai_job_end_to_end_never_claims_identity(
    test_client, test_db, tmp_path: Path, make_authenticated_headers
) -> None:
    """Manual/automated verification: run one real AI job end to end
    through the HTTP API and confirm no response text anywhere claims
    identity or recognition."""
    case = _make_case(test_db)
    recording = _make_recording_with_clip(test_db, case, tmp_path)
    headers = make_authenticated_headers()

    job_response = test_client.post(
        "/api/v1/ai/jobs",
        json={
            "case_id": case.id,
            "recording_ids": [recording.id],
            "analysis_types": ["object_detection", "motion_detection"],
            "sampling_strategy": "all",
        },
        headers=headers,
    )
    assert job_response.status_code == 200

    results_response = test_client.get(f"/api/v1/cases/{case.id}/ai-results", headers=headers)
    assert results_response.status_code == 200

    blob = (str(job_response.json()) + str(results_response.json())).lower()
    for forbidden in ("identity", "recognized", "recognition", "same person", "confirmed identity"):
        assert forbidden not in blob
