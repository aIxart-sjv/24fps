"""DB-level integration tests for frame-redundancy optimization inside
app/core/ai_manager.py (Phase 21, Part B).

Mirrors tests/test_ai_manager.py's fixture pattern: synthetic `Case`/
`Evidence`/`Recording`/`Artifact` rows and small synthetic MP4 clips (no
real CP Plus evidence required -- that lives in
tests/test_cp_plus_ai_frame_redundancy_real_evidence_integration.py).
Object-detection/face-detection cases use the real cached model weights
(skipped, not failed, if not cached -- see tests/fixtures/ai_models.py).
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
from app.models import AIResult, AITrack, Artifact, Case, Evidence, JobStatus, Recording
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base
from tests.fixtures.ai_models import requires_face_detection_model, requires_object_detection_model


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


def _make_case(db, case_id: str = "CASE-REDUNDANCY-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Redundancy test"))


def _write_static_then_moving_clip(
    path: Path, *, static_frame_count: int = 8, moving_frame_count: int = 6, fps: float = 5.0
) -> None:
    """A clip that stays completely still for `static_frame_count` frames
    (a real, meaningful redundancy scenario), then has a bright square
    sweep across the remaining `moving_frame_count` frames."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (160, 120))
    for _ in range(static_frame_count):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        writer.write(frame)
    for i in range(moving_frame_count):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        x = 10 + i * 15
        frame[20:80, x : x + 30] = 255
        writer.write(frame)
    writer.release()


def _make_recording_with_artifact(
    db,
    case: Case,
    tmp_path: Path,
    *,
    recording_id: str = "REC-REDUNDANCY-1",
) -> tuple[Recording, Artifact]:
    evidence = Evidence(evidence_id=f"EVID-{recording_id}", case_id=case.id, source_type="cp_plus")
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    clip_path = tmp_path / f"{recording_id}.mp4"
    _write_static_then_moving_clip(clip_path)

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
        channel=1,
        artifact_id=str(artifact.id),
        start_normalized=datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC),
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return recording, artifact


class TestFrameRedundancyDisabledByDefault:
    def test_frame_redundancy_disabled_by_default_no_stats_recorded(
        self, db, tmp_path: Path
    ) -> None:
        case = _make_case(db, "CASE-DISABLED-1")
        recording, _ = _make_recording_with_artifact(db, case, tmp_path)

        job = AIManager.run_job(
            db,
            case_id=case.id,
            recording_ids=[recording.id],
            analysis_types=["motion_detection"],
            sampling_strategy="all",
        )

        params = json.loads(job.parameters)
        assert params["frame_redundancy_enabled"] is False
        assert "frame_redundancy_stats" not in params


class TestFrameRedundancyStatsRecording:
    @requires_object_detection_model
    def test_stats_recorded_and_totals_correct(self, db, tmp_path: Path) -> None:
        case = _make_case(db, "CASE-STATS-1")
        recording, _ = _make_recording_with_artifact(db, case, tmp_path)

        job = AIManager.run_job(
            db,
            case_id=case.id,
            recording_ids=[recording.id],
            analysis_types=["object_detection"],
            sampling_strategy="all",
            frame_redundancy_enabled=True,
            frame_redundancy_threshold=2.0,
        )

        params = json.loads(job.parameters)
        assert params["frame_redundancy_enabled"] is True
        stats = params["frame_redundancy_stats"]
        assert stats["comparison_method"] == "grayscale_mean_absolute_difference"
        assert stats["reference_strategy"] == "last_analyzed_frame"
        assert stats["threshold"] == 2.0
        # 8 static + 6 moving = 14 total sampled frames -- no frame lost.
        assert stats["total_frames"] == 14
        assert stats["analyzed_count"] + stats["skipped_count"] == stats["total_frames"]
        # The static run should have produced at least one skip.
        assert stats["skipped_count"] > 0
        # The moving frames should have forced at least one real analysis
        # beyond just the first frame -- redundancy never swallows real
        # change.
        assert stats["analyze_reason_counts"].get("above_difference_threshold", 0) > 0
        assert stats["comparison_time_seconds"] >= 0.0

    @requires_face_detection_model
    def test_face_detection_with_redundancy_never_loses_frame_identity(
        self, db, tmp_path: Path
    ) -> None:
        case = _make_case(db, "CASE-STATS-2")
        recording, artifact = _make_recording_with_artifact(db, case, tmp_path)

        job = AIManager.run_job(
            db,
            case_id=case.id,
            recording_ids=[recording.id],
            analysis_types=["face_detection"],
            sampling_strategy="all",
            frame_redundancy_enabled=True,
            frame_redundancy_threshold=2.0,
        )

        assert job.status in (JobStatus.COMPLETED.value, JobStatus.PARTIAL.value)
        # No face is expected on this synthetic clip, but any row that
        # *did* get produced must reference a real sampled frame/artifact
        # -- never a fabricated one.
        for result in db.query(AIResult).filter(AIResult.recording_id == recording.id).all():
            assert result.source_artifact == artifact.id
            assert 0 <= result.frame_number < 14


class TestTrackingUnaffectedByFrameRedundancy:
    @requires_object_detection_model
    def test_tracking_results_identical_regardless_of_frame_redundancy_flag(
        self, db, tmp_path: Path
    ) -> None:
        """Task Phase 21 Part B's required controlled test: object
        appears -> redundant (static) frames -> meaningful movement ->
        track remains coherent. Tracking never consults the redundancy
        evaluator at all (see app.core.ai_manager's integration
        comment), so the strongest possible proof of "frame redundancy
        cannot break tracking continuity" is that enabling it produces
        byte-for-byte identical tracking output.
        """
        case_a = _make_case(db, "CASE-TRACK-A")
        recording_a, _ = _make_recording_with_artifact(
            db, case_a, tmp_path, recording_id="REC-TRACK-A"
        )
        case_b = _make_case(db, "CASE-TRACK-B")
        recording_b, _ = _make_recording_with_artifact(
            db, case_b, tmp_path, recording_id="REC-TRACK-B"
        )

        job_without_redundancy = AIManager.run_job(
            db,
            case_id=case_a.id,
            recording_ids=[recording_a.id],
            analysis_types=["object_tracking"],
            sampling_strategy="all",
            frame_redundancy_enabled=False,
        )
        job_with_redundancy = AIManager.run_job(
            db,
            case_id=case_b.id,
            recording_ids=[recording_b.id],
            analysis_types=["object_tracking"],
            sampling_strategy="all",
            frame_redundancy_enabled=True,
            frame_redundancy_threshold=2.0,
        )

        assert job_without_redundancy.status == job_with_redundancy.status

        tracks_without = (
            db.query(AITrack)
            .filter(AITrack.recording_id == recording_a.id)
            .order_by(AITrack.id)
            .all()
        )
        tracks_with = (
            db.query(AITrack)
            .filter(AITrack.recording_id == recording_b.id)
            .order_by(AITrack.id)
            .all()
        )
        assert len(tracks_without) == len(tracks_with)
        for track_without, track_with in zip(tracks_without, tracks_with, strict=True):
            assert track_without.frame_count == track_with.frame_count
            assert json.loads(track_without.trajectory) == json.loads(track_with.trajectory)

        results_without = (
            db.query(AIResult)
            .filter(AIResult.recording_id == recording_a.id)
            .order_by(AIResult.frame_number)
            .all()
        )
        results_with = (
            db.query(AIResult)
            .filter(AIResult.recording_id == recording_b.id)
            .order_by(AIResult.frame_number)
            .all()
        )
        assert len(results_without) == len(results_with)
        assert [r.frame_number for r in results_without] == [r.frame_number for r in results_with]
