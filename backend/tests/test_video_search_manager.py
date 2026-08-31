"""Tests for app/core/video_search_manager.py (Phase 23), against a small
synthetic clip with a known solid-color region -- no real evidence or
YOLO model weights required (the AI detection itself is pre-seeded
directly as `AIResult` rows, matching this module's own documented
contract that it never runs detection itself)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.case_manager import CaseManager
from app.core.video_search_manager import VideoSearchManager
from app.models import AIResult, Artifact, Case, Evidence, Recording
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base


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


def _make_case(db, case_id: str = "CASE-SEARCH-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Search test"))


def _write_clip_with_person(path: Path, *, bgr_shirt_color: tuple[int, int, int]) -> None:
    """A single 160x120 frame: a person-shaped region wearing a solid,
    known shirt color, on a neutral gray background."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 5.0, (160, 120))
    frame = np.full((120, 160, 3), 128, dtype=np.uint8)  # neutral gray background
    frame[20:100, 50:110] = bgr_shirt_color  # the "person" bbox region
    for _ in range(3):
        writer.write(frame)
    writer.release()


def _make_recording_with_ai_result(
    db,
    case: Case,
    tmp_path: Path,
    *,
    recording_id: str,
    bgr_shirt_color: tuple[int, int, int],
    class_name: str = "person",
    frame_number: int = 0,
) -> AIResult:
    evidence = Evidence(
        evidence_id=f"EVID-{recording_id}", case_id=case.id, source_type="native_export"
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    clip_path = tmp_path / f"{recording_id}.mp4"
    _write_clip_with_person(clip_path, bgr_shirt_color=bgr_shirt_color)

    artifact = Artifact(
        evidence_id=evidence.id,
        artifact_type="cp_plus_h264_preview_mp4",
        path=str(clip_path),
        size_bytes=clip_path.stat().st_size,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    recording = Recording(evidence_id=evidence.id, recording_id=recording_id, camera_id="CAM-1")
    db.add(recording)
    db.commit()
    db.refresh(recording)

    ai_result = AIResult(
        case_id=case.id,
        recording_id=recording.id,
        analysis_type="object_detection",
        model_name="yolov8n",
        model_version="test",
        frame_number=frame_number,
        class_name=class_name,
        confidence=0.9,
        bbox_x_min=50,
        bbox_y_min=20,
        bbox_x_max=110,
        bbox_y_max=100,
        source_artifact=artifact.id,
    )
    db.add(ai_result)
    db.commit()
    db.refresh(ai_result)
    return ai_result


def test_search_matches_red_shirt_detection(db, tmp_path: Path) -> None:
    case = _make_case(db)
    _make_recording_with_ai_result(
        db, case, tmp_path, recording_id="REC-RED", bgr_shirt_color=(0, 0, 255)
    )

    result = VideoSearchManager.search(db, case_id=case.id, query="red shirt guy")

    assert result.recognized is True
    assert result.detections_examined == 1
    assert len(result.sightings) == 1
    assert result.sightings[0].matched_color == "red"
    assert result.sightings[0].camera_id == "CAM-1"


def test_search_does_not_match_wrong_color(db, tmp_path: Path) -> None:
    case = _make_case(db)
    _make_recording_with_ai_result(
        db, case, tmp_path, recording_id="REC-BLUE", bgr_shirt_color=(255, 0, 0)
    )

    result = VideoSearchManager.search(db, case_id=case.id, query="red shirt guy")

    assert result.recognized is True
    assert result.sightings == []
    assert result.warnings


def test_search_unrecognized_query_reports_supported_vocabulary(db) -> None:
    case = _make_case(db)
    result = VideoSearchManager.search(db, case_id=case.id, query="someone suspicious")

    assert result.recognized is False
    assert result.sightings == []
    assert "red" in result.supported_colors


def test_search_with_no_ai_results_reports_honest_warning(db) -> None:
    case = _make_case(db)
    result = VideoSearchManager.search(db, case_id=case.id, query="red shirt guy")

    assert result.recognized is True
    assert result.detections_examined == 0
    assert result.sightings == []
    assert any("run AI analysis" in w for w in result.warnings)


def test_search_result_is_traceable_to_ai_result_id(db, tmp_path: Path) -> None:
    case = _make_case(db)
    ai_result = _make_recording_with_ai_result(
        db, case, tmp_path, recording_id="REC-TRACE", bgr_shirt_color=(0, 0, 255)
    )

    result = VideoSearchManager.search(db, case_id=case.id, query="red shirt guy")

    assert result.sightings[0].ai_result_ids == [ai_result.id]
    # Phase 24 task scope, "Search Result Details": class/source artifact
    # must be present per-row, not only on the parent query response.
    assert result.sightings[0].class_name == ai_result.class_name
    assert result.sightings[0].source_artifact == ai_result.source_artifact
