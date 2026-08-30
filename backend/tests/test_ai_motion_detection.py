"""Tests for app/ai/motion_detection.py (Phase 13) -- deterministic
frame-differencing over synthetic numpy frames, no real video needed."""

from __future__ import annotations

import numpy as np

from app.ai.motion_detection import DEFAULT_MIN_AREA, DEFAULT_THRESHOLD, detect_motion_events


def _blank_frame(size: int = 100) -> np.ndarray:
    return np.zeros((size, size, 3), dtype=np.uint8)


def _frame_with_square(*, size: int = 100, x: int, square_size: int = 20) -> np.ndarray:
    frame = _blank_frame(size)
    frame[10 : 10 + square_size, x : x + square_size] = 255
    return frame


def test_identical_frames_produce_no_motion_events() -> None:
    frame = _blank_frame()
    samples = [(i, i / 5.0, frame.copy()) for i in range(5)]

    events = detect_motion_events(samples)

    assert events == []


def test_moving_object_produces_one_contiguous_motion_event() -> None:
    # Background, then a square sweeping across 3 frames, then background
    # again -- one contiguous motion span, not several.
    samples = [
        (0, 0.0, _blank_frame()),
        (1, 0.2, _frame_with_square(x=10)),
        (2, 0.4, _frame_with_square(x=30)),
        (3, 0.6, _frame_with_square(x=50)),
        (4, 0.8, _blank_frame()),
        (5, 1.0, _blank_frame()),
    ]

    events = detect_motion_events(samples)

    assert len(events) == 1
    event = events[0]
    assert event.start_time_seconds == 0.0
    assert event.end_time_seconds == 0.8
    assert event.regions
    assert event.score > 0


def test_motion_regions_use_the_structured_bounding_box_representation() -> None:
    samples = [
        (0, 0.0, _blank_frame()),
        (1, 0.2, _frame_with_square(x=10)),
    ]

    events = detect_motion_events(samples)

    assert len(events) == 1
    region = events[0].regions[0]
    assert region.bbox.x_max > region.bbox.x_min
    assert region.bbox.y_max > region.bbox.y_min
    assert region.frame_number == 1
    assert region.timestamp_seconds == 0.2


def test_two_separate_motion_bursts_produce_two_events() -> None:
    samples = [
        (0, 0.0, _blank_frame()),
        (1, 0.2, _frame_with_square(x=10)),
        (2, 0.4, _blank_frame()),
        (3, 0.6, _blank_frame()),
        (4, 0.8, _frame_with_square(x=60)),
        (5, 1.0, _blank_frame()),
    ]

    events = detect_motion_events(samples)

    assert len(events) == 2


def test_fewer_than_two_samples_yields_no_events() -> None:
    assert detect_motion_events([]) == []
    assert detect_motion_events([(0, 0.0, _blank_frame())]) == []


def test_small_change_below_min_area_is_not_reported_as_motion() -> None:
    frame = _blank_frame()
    tiny_change = frame.copy()
    tiny_change[0:2, 0:2] = 255  # 4 pixels -- well under DEFAULT_MIN_AREA

    events = detect_motion_events([(0, 0.0, frame), (1, 0.1, tiny_change)])

    assert events == []


def test_method_and_parameters_are_the_documented_constants() -> None:
    # These are recorded on the persisted MotionEvent row by
    # app.core.ai_manager -- protecting the exact constant names/values
    # here keeps that reproducibility metadata honest.
    assert DEFAULT_THRESHOLD == 25
    assert DEFAULT_MIN_AREA == 500.0
