"""Tests for app/core/validation_manager.py's `run_validation` (Phase 14)
-- DB-level, against synthetic `GroundTruth` and system-output rows for
every validation type."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.types import BoundingBox
from app.core.case_manager import CaseManager
from app.core.correlation_manager import CorrelationManager
from app.core.timeline_manager import TimelineManager
from app.core.validation_manager import ValidationManager
from app.models import (
    AIResult,
    AITrack,
    Artifact,
    Case,
    Evidence,
    JobStatus,
    MotionEvent,
    Recording,
    RecoveryResult,
)
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base
from app.timeline.correlation import CameraTopology

_T0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)


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


def _make_case(db, case_id: str = "CASE-VAL-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Validation test"))


def _make_recording(db, case: Case, *, recording_id: str = "REC-1") -> tuple[Recording, Artifact]:
    evidence = Evidence(evidence_id=f"EVID-{recording_id}", case_id=case.id, source_type="cp_plus")
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    artifact = Artifact(
        evidence_id=evidence.id, artifact_type="cp_plus_h264_preview_mp4", path="/x"
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    recording = Recording(
        evidence_id=evidence.id,
        recording_id=recording_id,
        start_normalized=_T0,
        start_original=_T0,
        end_original=_T0 + timedelta(seconds=10),
        duration_ms=10000,
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return recording, artifact


def test_run_validation_rejects_unrecognized_type(db) -> None:
    case = _make_case(db)
    with pytest.raises(ValueError, match="unrecognized validation_type"):
        ValidationManager.run_validation(
            db, case_id=case.id, validation_type="not_a_real_type", dataset_id="DS-1"
        )


def test_run_validation_with_no_ground_truth_fails(db) -> None:
    case = _make_case(db)
    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="object_detection", dataset_id="NO-SUCH-DATASET"
    )
    assert job.status == JobStatus.FAILED.value
    assert "no ground truth found" in (job.error or "")
    assert metrics == []


def test_run_validation_records_reproducibility_metadata(db) -> None:
    case = _make_case(db)
    recording, artifact = _make_recording(db, case)
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-1",
        event_type="object_detection",
        recording_id=recording.id,
        object_class="person",
        frame_number=0,
        bbox=BoundingBox(0, 0, 10, 10),
        source_reference="controlled test",
    )
    job, _ = ValidationManager.run_validation(
        db,
        case_id=case.id,
        validation_type="object_detection",
        dataset_id="DS-1",
        iou_threshold=0.6,
    )
    parameters = json.loads(job.parameters)
    assert parameters["validation_type"] == "object_detection"
    assert parameters["dataset_id"] == "DS-1"
    assert parameters["iou_threshold"] == 0.6
    assert job.software_version is not None
    assert job.started_at is not None
    assert job.completed_at is not None


def test_object_detection_validation_end_to_end(db) -> None:
    case = _make_case(db)
    recording, artifact = _make_recording(db, case)
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-OBJ",
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
    db.add(prediction)
    db.commit()

    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="object_detection", dataset_id="DS-OBJ"
    )

    assert job.status == JobStatus.COMPLETED.value
    values = {m.metric_name: m.metric_value for m in metrics}
    assert values["object_detection.true_positives"] == 1.0
    assert values["object_detection.precision"] == 1.0
    assert values["object_detection.recall"] == 1.0


def test_object_detection_validation_with_no_predictions_reports_all_false_negatives(db) -> None:
    case = _make_case(db)
    recording, _ = _make_recording(db, case)
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-MISS",
        event_type="object_detection",
        recording_id=recording.id,
        object_class="person",
        frame_number=0,
        bbox=BoundingBox(0, 0, 10, 10),
        source_reference="controlled test",
    )
    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="object_detection", dataset_id="DS-MISS"
    )
    # A legitimate, honest outcome -- not an operational failure.
    assert job.status == JobStatus.COMPLETED.value
    values = {m.metric_name: m.metric_value for m in metrics}
    assert values["object_detection.false_negatives"] == 1.0
    assert values["object_detection.true_positives"] == 0.0


def test_motion_validation_end_to_end(db) -> None:
    case = _make_case(db)
    recording, artifact = _make_recording(db, case)
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-MOT",
        event_type="motion",
        recording_id=recording.id,
        expected_start=_T0,
        expected_end=_T0 + timedelta(seconds=5),
        source_reference="controlled test",
    )
    event = MotionEvent(
        case_id=case.id,
        recording_id=recording.id,
        start_time=_T0,
        end_time=_T0 + timedelta(seconds=5),
        method="frame_differencing",
        source_artifact=artifact.id,
    )
    db.add(event)
    db.commit()

    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="motion", dataset_id="DS-MOT"
    )
    assert job.status == JobStatus.COMPLETED.value
    values = {m.metric_name: m.metric_value for m in metrics}
    assert values["motion.true_positives"] == 1.0


def test_tracking_validation_end_to_end(db) -> None:
    case = _make_case(db)
    recording, artifact = _make_recording(db, case)
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-TRK",
        event_type="tracking",
        recording_id=recording.id,
        object_class="person",
        frame_number=0,
        expected_frames=9,
        group_reference="TRACK-1",
        source_reference="controlled test",
    )
    track = AITrack(
        case_id=case.id,
        recording_id=recording.id,
        camera_id="1",
        track_id=1,
        class_name="person",
        first_seen_frame=0,
        last_seen_frame=9,
        frame_count=10,
        average_confidence=0.8,
        model_version="yolov8n",
        tracker_version="bytetrack",
        source_artifact=artifact.id,
    )
    db.add(track)
    db.commit()

    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="tracking", dataset_id="DS-TRK"
    )
    assert job.status == JobStatus.COMPLETED.value
    values = {m.metric_name: m.metric_value for m in metrics}
    assert values["tracking.TRACK-1.coverage_fraction"] == 1.0


def test_recovery_validation_end_to_end(db) -> None:
    case = _make_case(db)
    recording, _ = _make_recording(db, case)
    evidence = db.query(Evidence).filter(Evidence.id == recording.evidence_id).first()
    result = RecoveryResult(
        evidence_id=evidence.id,
        recording_id=recording.id,
        method="filesystem_recovery",
        status="recovered",
        frames_recovered=95,
        fragments_found=1,
        fragments_used=1,
        recovery_rate=0.95,
        frame_continuity=0.98,
    )
    db.add(result)
    db.commit()
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-REC",
        event_type="recovery",
        recording_id=recording.id,
        expected_frames=100,
        expected_fragments=1,
        source_reference="controlled test",
    )

    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="recovery", dataset_id="DS-REC"
    )
    assert job.status == JobStatus.COMPLETED.value
    values = {m.metric_name: m.metric_value for m in metrics}
    assert values["recovery.recording_1.frames_error"] == -5.0


def test_timeline_validation_end_to_end(db) -> None:
    case = _make_case(db)
    recording, _ = _make_recording(db, case)
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-TL",
        event_type="timeline",
        recording_id=recording.id,
        timestamp=_T0,
        source_reference="controlled test",
    )
    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="timeline", dataset_id="DS-TL"
    )
    assert job.status == JobStatus.COMPLETED.value
    values = {m.metric_name: m.metric_value for m in metrics}
    assert values["timeline.error_seconds.recording_1"] == 0.0


def test_correlation_validation_end_to_end(db) -> None:
    case = _make_case(db)
    TimelineManager.create_examiner_marker(
        db, case_id=case.id, camera_id="A", recording_id=None, timestamp=_T0, description="A"
    )
    TimelineManager.create_examiner_marker(
        db,
        case_id=case.id,
        camera_id="B",
        recording_id=None,
        timestamp=_T0 + timedelta(seconds=7),
        description="B",
    )
    TimelineManager.create_examiner_marker(
        db,
        case_id=case.id,
        camera_id="C",
        recording_id=None,
        timestamp=_T0 + timedelta(seconds=19),
        description="C",
    )
    topology = CameraTopology(transitions={("A", "B"): None, ("B", "C"): None})
    CorrelationManager.run_correlation(db, case.id, topology=topology)

    for camera_id, offset in (("A", 0), ("B", 7), ("C", 19)):
        ValidationManager.create_ground_truth(
            db,
            case_id=case.id,
            dataset_id="DS-CORR",
            event_type="correlation",
            camera_id=camera_id,
            timestamp=_T0 + timedelta(seconds=offset),
            group_reference="SEQ-1",
            source_reference="controlled A->B->C scenario",
        )

    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="correlation", dataset_id="DS-CORR"
    )
    assert job.status == JobStatus.COMPLETED.value
    values = {m.metric_name: m.metric_value for m in metrics}
    assert values["correlation.true_positives"] == 1.0


def test_vendor_parser_validation_end_to_end(db) -> None:
    case = _make_case(db)
    recording, artifact = _make_recording(db, case)
    recording.artifact_id = str(artifact.id)
    db.add(recording)
    db.commit()
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-VEND",
        event_type="vendor_parser",
        recording_id=recording.id,
        source_reference="real evidence",
    )
    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="vendor_parser", dataset_id="DS-VEND"
    )
    assert job.status == JobStatus.COMPLETED.value
    values = {m.metric_name: m.metric_value for m in metrics}
    assert values["vendor_parser.recording_1.file_recognized"] == 1.0
    assert values["vendor_parser.recording_1.extraction_compatible"] == 1.0


def test_list_validation_metrics_filters(db) -> None:
    case = _make_case(db)
    recording, _ = _make_recording(db, case)
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-TL",
        event_type="timeline",
        recording_id=recording.id,
        timestamp=_T0,
        source_reference="controlled",
    )
    job, _ = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="timeline", dataset_id="DS-TL"
    )

    all_metrics = ValidationManager.list_validation_metrics(db, case.id)
    by_job = ValidationManager.list_validation_metrics(db, case.id, job_id=job.id)
    by_type = ValidationManager.list_validation_metrics(db, case.id, validation_type="timeline")
    by_wrong_type = ValidationManager.list_validation_metrics(
        db, case.id, validation_type="recovery"
    )

    assert len(all_metrics) > 0
    assert len(by_job) == len(all_metrics)
    assert len(by_type) == len(all_metrics)
    assert by_wrong_type == []
