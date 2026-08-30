"""Tests for app/ai/tracking.py (Phase 13).

Master Specification Section 32: "Tracking does not automatically prove
identity." These tests protect that no field on `Track`/`TrackPoint`
carries an identity claim, and exercise the real `run_tracking` adapter
end to end (skipped, not failed, when the YOLO weights are not already
cached -- see `tests/fixtures/ai_models.py`).
"""

from __future__ import annotations

import dataclasses

import numpy as np

from app.ai.tracking import BOTSORT_TRACKER, BYTETRACK_TRACKER, run_tracking
from app.ai.types import BoundingBox, Track, TrackPoint
from tests.fixtures.ai_models import requires_object_detection_model


def test_track_dataclass_has_no_identity_field() -> None:
    field_names = {f.name for f in dataclasses.fields(Track)}

    for forbidden in ("identity", "name", "person_id", "embedding", "face", "recognized"):
        assert forbidden not in field_names


def test_track_dataclass_shape() -> None:
    point = TrackPoint(
        frame_number=5,
        timestamp_seconds=0.2,
        bbox=BoundingBox(x_min=0.0, y_min=0.0, x_max=10.0, y_max=10.0),
        confidence=0.5,
    )
    track = Track(
        track_id=1,
        class_name="person",
        first_seen_frame=0,
        first_seen_timestamp_seconds=0.0,
        last_seen_frame=5,
        last_seen_timestamp_seconds=0.2,
        trajectory=[point],
        frame_count=1,
        average_confidence=0.5,
    )

    assert track.track_id == 1
    assert track.frame_count == len(track.trajectory)
    assert track.last_seen_frame >= track.first_seen_frame


def test_run_tracking_with_no_frames_returns_empty_list() -> None:
    assert run_tracking(model=None, frames=[]) == []


@requires_object_detection_model
def test_run_tracking_on_blank_frames_finds_no_tracks() -> None:
    from app.ai.model_registry import load_object_detection_model
    from app.config import get_settings

    model = load_object_detection_model(get_settings().ai_model_root, device="cpu")
    assert model.available

    blank = np.zeros((240, 320, 3), dtype=np.uint8)
    frames = [(i, i / 5.0, blank.copy()) for i in range(3)]

    tracks = run_tracking(model.model, frames, tracker=BYTETRACK_TRACKER, device="cpu")

    assert tracks == []


@requires_object_detection_model
def test_run_tracking_accepts_botsort_tracker_without_error() -> None:
    from app.ai.model_registry import load_object_detection_model
    from app.config import get_settings

    model = load_object_detection_model(get_settings().ai_model_root, device="cpu")
    assert model.available

    blank = np.zeros((240, 320, 3), dtype=np.uint8)
    frames = [(0, 0.0, blank)]

    tracks = run_tracking(model.model, frames, tracker=BOTSORT_TRACKER, device="cpu")

    assert isinstance(tracks, list)
