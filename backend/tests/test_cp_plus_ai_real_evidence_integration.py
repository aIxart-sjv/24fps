"""Real CP Plus evidence -- Phase 13 acceptance test.

Demonstrates a real recording passing through the full Phase 13 pipeline:

    Recording Artifact (Phase 9 output)
      -> frame selection (app.ai.frame_sampling)
      -> motion detection and/or object detection
      -> persisted AIResult/MotionEvent rows
      -> source_artifact references back to the exact derived MP4 used

This evidence package (`~/Documents/24fps-evidence/cp-plus-2026-08-28/`) is
real, hash-verified, single-NVR/single-channel CP Plus footage. That is
sufficient to validate the AI processing pipeline end to end against real
video, but it does NOT and cannot validate cross-camera AI tracking or
real multi-camera identity/correlation -- this file states that plainly
rather than fabricating a multi-camera claim, exactly as Phase 12's real-
evidence test did for cross-camera correlation.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.ai_manager import AIManager
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.models import AIResult, JobStatus, MotionEvent
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from tests.fixtures.ai_models import requires_object_detection_model
from tests.fixtures.cp_plus_evidence import (
    load_expected_sha256,
    requires_real_evidence,
    sha256_of,
    smallest_real_cpv_path,
)

#: This evidence package cannot and does not validate real cross-camera
#: AI tracking or multi-camera identity/correlation -- stated explicitly
#: rather than fabricated, per this phase's own requirement.
REAL_MULTI_CAMERA_AI_VALIDATION_STATEMENT = (
    "Real single-channel CP Plus recording validated end to end through "
    "frame selection, AI analysis, and source-artifact traceability; "
    "cross-camera AI tracking and real multi-camera identity/correlation "
    "remain unvalidated by this evidence package."
)


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Matches the established pattern from
    tests/test_cp_plus_timeline_real_evidence_integration.py."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    evidence_root = tmp_path / "evidence"
    artifact_root = tmp_path / "artifacts"
    evidence_root.mkdir()
    artifact_root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import app.models  # noqa: F401 - registers every ORM model on Base.metadata

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    try:
        yield db, evidence_root
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        get_settings.cache_clear()


def test_real_multi_camera_ai_validation_is_explicitly_pending() -> None:
    assert "cross-camera AI tracking" in REAL_MULTI_CAMERA_AI_VALIDATION_STATEMENT
    assert "remain unvalidated" in REAL_MULTI_CAMERA_AI_VALIDATION_STATEMENT


def _register_real_recording(db, evidence_root: Path, case_id: str):
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    expected_hashes = load_expected_sha256()
    assert sha256_of(source_path) == expected_hashes[source_path.name]

    case_dir = evidence_root / case_id
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="AI IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]
    # Phase 9's extraction step (FFmpeg mux/transcode) is a separate call
    # from enumeration -- AI needs the resulting derived MP4 artifact to
    # decode frames from.
    recording = RecordingManager.extract_recording(db, recording.id)
    return case, recording, source_path, copied_path, expected_hashes


@requires_real_evidence
def test_real_recording_motion_detection_pipeline(real_evidence_db) -> None:
    db, evidence_root = real_evidence_db
    case, recording, source_path, copied_path, expected_hashes = _register_real_recording(
        db, evidence_root, "CASE-AI-MOTION"
    )
    assert recording.artifact_id is not None  # Phase 9 produced a derived MP4

    job = AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id],
        analysis_types=["motion_detection"],
        sampling_strategy="fps",
        sampling_value=5.0,
    )

    # A real, short CP Plus segment may or may not contain detectable
    # motion -- either outcome is honest; what matters is the job actually
    # ran against real video and completed (not failed to even open it).
    assert job.status in (JobStatus.COMPLETED.value, JobStatus.PARTIAL.value)
    assert job.worker in ("cpu", "cuda:0")

    events = db.query(MotionEvent).filter(MotionEvent.recording_id == recording.id).all()
    for event in events:
        assert event.source_artifact is not None
        assert event.case_id == case.id

    # Source evidence is provably unmodified by the entire pipeline.
    assert sha256_of(copied_path) == expected_hashes[source_path.name]
    assert sha256_of(source_path) == expected_hashes[source_path.name]


@requires_real_evidence
@requires_object_detection_model
def test_real_recording_object_detection_pipeline(real_evidence_db) -> None:
    db, evidence_root = real_evidence_db
    case, recording, source_path, copied_path, expected_hashes = _register_real_recording(
        db, evidence_root, "CASE-AI-OBJDET"
    )

    job = AIManager.run_job(
        db,
        case_id=case.id,
        recording_ids=[recording.id],
        analysis_types=["object_detection"],
        sampling_strategy="fps",
        sampling_value=5.0,
    )

    assert job.status in (JobStatus.COMPLETED.value, JobStatus.PARTIAL.value)
    assert job.model_versions is not None
    assert "yolov8n.pt" in job.model_versions

    # Every result, whether zero or more were found, must trace back to
    # the real derived artifact actually decoded -- never a fabricated
    # or disconnected source reference.
    results = db.query(AIResult).filter(AIResult.recording_id == recording.id).all()
    for result in results:
        assert result.source_artifact is not None
        assert result.job_id == job.id
        assert result.model_name == "yolov8n.pt"

    assert sha256_of(copied_path) == expected_hashes[source_path.name]
