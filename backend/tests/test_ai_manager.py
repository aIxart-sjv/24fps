"""Tests for app/core/ai_manager.py (Phase 13) -- DB-level, against
synthetic `Case`/`Evidence`/`Recording`/`Artifact` rows and small
synthetic MP4 clips (no real CP Plus evidence required; that lives in
tests/test_cp_plus_ai_real_evidence_integration.py).

Motion detection needs no model, so most of this file runs unconditionally.
Object-detection/tracking cases are marked and skipped (not failed) when
the YOLO weights are not already cached -- see tests/fixtures/ai_models.py.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.ai_manager import AIManager
from app.core.case_manager import CaseManager
from app.models import (
    AIResult,
    AITrack,
    Artifact,
    Case,
    Evidence,
    JobStatus,
    MotionEvent,
    Recording,
)
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base
from tests.fixtures.ai_models import requires_object_detection_model


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _make_case(db, case_id: str = "CASE-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Test case"))


def _write_synthetic_clip(
    path: Path, *, moving: bool, frame_count: int = 10, fps: float = 5.0
) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (160, 120))
    for i in range(frame_count):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        if moving:
            x = 10 + (i * 10) % 100
            frame[20:60, x : x + 30] = 255
        writer.write(frame)
    writer.release()


def _make_recording_with_artifact(
    db,
    case: Case,
    tmp_path: Path,
    *,
    recording_id: str = "REC-1",
    moving: bool = True,
    channel: int | None = 1,
    camera_id: str | None = None,
    with_normalized_start: bool = True,
) -> tuple[Recording, Artifact]:
    evidence = Evidence(evidence_id=f"EVID-{recording_id}", case_id=case.id, source_type="cp_plus")
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    clip_path = tmp_path / f"{recording_id}.mp4"
    _write_synthetic_clip(clip_path, moving=moving)

    artifact = Artifact(
        evidence_id=evidence.id,
        artifact_type="cp_plus_h264_preview_mp4",
        path=str(clip_path),
        size_bytes=clip_path.stat().st_size,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    recording = Recording(
        evidence_id=evidence.id,
        recording_id=recording_id,
        camera_id=camera_id,
        channel=channel,
        artifact_id=str(artifact.id),
        start_normalized=(
            datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC) if with_normalized_start else None
        ),
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return recording, artifact


def test_run_job_rejects_empty_recording_ids(db) -> None:
    case = _make_case(db)
    with pytest.raises(ValueError, match="recording_ids"):
        AIManager.run_job(
            db, case_id=case.id, recording_ids=[], analysis_types=["motion_detection"]
        )


def test_run_job_rejects_unrecognized_analysis_type(db) -> None:
    case = _make_case(db)
    with pytest.raises(ValueError, match="unrecognized analysis type"):
        AIManager.run_job(
            db, case_id=case.id, recording_ids=[1], analysis_types=["not_a_real_type"]
        )


def test_run_job_motion_detection_completes_and_persists_events(db, tmp_path: Path) -> None:
    case = _make_case(db)
    recording, artifact = _make_recording_with_artifact(db, case, tmp_path, moving=True)

    job = AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id],
        analysis_types=["motion_detection"],
        sampling_strategy="all",
    )

    assert job.status == JobStatus.COMPLETED.value
    assert job.completed_at is not None
    assert job.worker in ("cpu", "cuda:0")

    events = db.query(MotionEvent).filter(MotionEvent.recording_id == recording.id).all()
    assert len(events) >= 1
    event = events[0]
    assert event.case_id == case.id
    assert event.source_artifact == artifact.id
    assert event.method == "frame_differencing"
    assert json.loads(event.parameters)["threshold"] == 25
    assert event.start_time is not None  # normalized start was available


def test_run_job_records_camera_id_from_channel_fallback(db, tmp_path: Path) -> None:
    case = _make_case(db)
    recording, _ = _make_recording_with_artifact(
        db, case, tmp_path, moving=True, camera_id=None, channel=7
    )

    AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id],
        analysis_types=["motion_detection"],
        sampling_strategy="all",
    )

    events = db.query(MotionEvent).filter(MotionEvent.recording_id == recording.id).all()
    assert events
    assert events[0].camera_id == "7"


def test_run_job_without_normalized_start_leaves_timestamps_null(db, tmp_path: Path) -> None:
    case = _make_case(db)
    recording, _ = _make_recording_with_artifact(
        db, case, tmp_path, moving=True, with_normalized_start=False
    )

    AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id],
        analysis_types=["motion_detection"],
        sampling_strategy="all",
    )

    events = db.query(MotionEvent).filter(MotionEvent.recording_id == recording.id).all()
    assert events
    # Never fabricated: no normalized start means no absolute timestamp.
    assert events[0].start_time is None
    assert events[0].end_time is None


def test_run_job_missing_recording_is_reported_and_job_fails(db) -> None:
    case = _make_case(db)

    job = AIManager.run_job(
        db, case_id=case.id, recording_ids=[999999], analysis_types=["motion_detection"]
    )

    assert job.status == JobStatus.FAILED.value
    assert job.error is not None
    assert "999999" in job.error


def test_run_job_mixed_valid_and_missing_recordings_is_partial(db, tmp_path: Path) -> None:
    case = _make_case(db)
    recording, _ = _make_recording_with_artifact(db, case, tmp_path, moving=True)

    job = AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id, 999999],
        analysis_types=["motion_detection"],
        sampling_strategy="all",
    )

    assert job.status == JobStatus.PARTIAL.value
    assert job.results_count >= 1
    assert job.warnings is not None
    assert "999999" in job.warnings


def test_run_job_recording_with_no_source_artifact_is_reported(db) -> None:
    case = _make_case(db)
    evidence = Evidence(evidence_id="EVID-NOART", case_id=case.id, source_type="cp_plus")
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    recording = Recording(evidence_id=evidence.id, recording_id="REC-NOART", artifact_id=None)
    db.add(recording)
    db.commit()
    db.refresh(recording)

    job = AIManager.run_job(
        db, case_id=case.id, recording_ids=[recording.id], analysis_types=["motion_detection"]
    )

    assert job.status == JobStatus.FAILED.value
    assert "no derived artifact available" in (job.error or "")


def test_run_job_decoder_failure_on_non_video_artifact_is_reported(db, tmp_path: Path) -> None:
    case = _make_case(db)
    evidence = Evidence(evidence_id="EVID-BADFILE", case_id=case.id, source_type="cp_plus")
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    not_a_video = tmp_path / "not_a_video.mp4"
    not_a_video.write_bytes(b"this is not a real video file")
    artifact = Artifact(
        evidence_id=evidence.id, artifact_type="cp_plus_h264_preview_mp4", path=str(not_a_video)
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    recording = Recording(
        evidence_id=evidence.id, recording_id="REC-BADFILE", artifact_id=str(artifact.id)
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)

    job = AIManager.run_job(
        db, case_id=case.id, recording_ids=[recording.id], analysis_types=["motion_detection"]
    )

    assert job.status == JobStatus.FAILED.value
    assert "decoder failure" in (job.error or "")


def test_list_ai_results_filters_by_recording_and_analysis_type(db, tmp_path: Path) -> None:
    case = _make_case(db)
    recording, artifact = _make_recording_with_artifact(db, case, tmp_path, moving=True)

    # No model needed: insert AIResult rows directly to test the query layer.
    row = AIResult(
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
    db.add(row)
    db.commit()

    all_results = AIManager.list_ai_results(db, case.id)
    filtered_by_recording = AIManager.list_ai_results(db, case.id, recording_id=recording.id)
    filtered_by_type = AIManager.list_ai_results(db, case.id, analysis_type="object_detection")
    filtered_by_wrong_type = AIManager.list_ai_results(db, case.id, analysis_type="face_detection")

    assert len(all_results) == 1
    assert len(filtered_by_recording) == 1
    assert len(filtered_by_type) == 1
    assert filtered_by_wrong_type == []


@requires_object_detection_model
def test_run_job_object_detection_records_model_version(db, tmp_path: Path) -> None:
    case = _make_case(db)
    recording, artifact = _make_recording_with_artifact(db, case, tmp_path, moving=True)

    job = AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id],
        analysis_types=["object_detection"],
        sampling_strategy="all",
    )

    assert job.status in (JobStatus.COMPLETED.value, JobStatus.PARTIAL.value)
    assert job.model_versions is not None
    assert "yolov8n.pt" in json.loads(job.model_versions)
    # Every AIResult (if any were produced on this synthetic clip) traces
    # back to the exact source artifact used.
    for result in db.query(AIResult).filter(AIResult.recording_id == recording.id).all():
        assert result.source_artifact == artifact.id
        assert result.job_id == job.id


@requires_object_detection_model
def test_run_job_object_tracking_persists_tracks_linked_to_results(db, tmp_path: Path) -> None:
    case = _make_case(db)
    recording, artifact = _make_recording_with_artifact(db, case, tmp_path, moving=True)

    job = AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id],
        analysis_types=["object_tracking"],
        sampling_strategy="all",
    )

    assert job.status in (JobStatus.COMPLETED.value, JobStatus.PARTIAL.value)
    tracks = db.query(AITrack).filter(AITrack.recording_id == recording.id).all()
    for track in tracks:
        assert track.source_artifact == artifact.id
        assert track.frame_count == len(json.loads(track.trajectory))
        linked_results = db.query(AIResult).filter(AIResult.track_id == track.id).all()
        assert len(linked_results) == track.frame_count
        for result in linked_results:
            assert result.analysis_type == "object_tracking"
