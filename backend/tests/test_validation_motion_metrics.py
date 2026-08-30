"""Tests for app/validation/motion_metrics.py (Phase 14) -- motion-event
validation: temporal IoU matching, timing error, false/missed motion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.validation.ground_truth import GroundTruthMotionEvent
from app.validation.motion_metrics import SystemMotionEvent, match_motion_events, temporal_iou

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_temporal_iou_identical_intervals_is_one() -> None:
    a = GroundTruthMotionEvent(start_time=_T0, end_time=_T0 + timedelta(seconds=10))
    assert temporal_iou(a, a) == 1.0


def test_temporal_iou_non_overlapping_is_zero() -> None:
    a = GroundTruthMotionEvent(start_time=_T0, end_time=_T0 + timedelta(seconds=5))
    b = GroundTruthMotionEvent(
        start_time=_T0 + timedelta(seconds=10), end_time=_T0 + timedelta(seconds=15)
    )
    assert temporal_iou(a, b) == 0.0


def test_detected_event_matching_expected_is_true_positive() -> None:
    ground_truth = [GroundTruthMotionEvent(start_time=_T0, end_time=_T0 + timedelta(seconds=10))]
    system_events = [
        SystemMotionEvent(
            start_time=_T0 + timedelta(seconds=1), end_time=_T0 + timedelta(seconds=11)
        )
    ]
    result = match_motion_events(ground_truth, system_events)
    assert result.counts.tp == 1
    assert result.counts.fp == 0
    assert result.counts.fn == 0


def test_timing_error_is_computed_for_matched_pairs() -> None:
    ground_truth = [GroundTruthMotionEvent(start_time=_T0, end_time=_T0 + timedelta(seconds=10))]
    system_events = [
        SystemMotionEvent(
            start_time=_T0 + timedelta(milliseconds=180), end_time=_T0 + timedelta(seconds=10)
        )
    ]
    result = match_motion_events(ground_truth, system_events)
    assert result.matches[0].start_error_seconds == pytest.approx(0.18)
    assert result.matches[0].end_error_seconds == pytest.approx(0.0)


def test_false_positive_motion_event() -> None:
    system_events = [SystemMotionEvent(start_time=_T0, end_time=_T0 + timedelta(seconds=5))]
    result = match_motion_events([], system_events)
    assert result.counts.tp == 0
    assert result.counts.fp == 1
    assert result.counts.fn == 0


def test_missed_motion_event_is_false_negative() -> None:
    ground_truth = [GroundTruthMotionEvent(start_time=_T0, end_time=_T0 + timedelta(seconds=5))]
    result = match_motion_events(ground_truth, [])
    assert result.counts.tp == 0
    assert result.counts.fn == 1
    assert result.counts.fp == 0


def test_configurable_overlap_threshold() -> None:
    ground_truth = [GroundTruthMotionEvent(start_time=_T0, end_time=_T0 + timedelta(seconds=10))]
    # overlap: intersection [5,10]=5s, union [0,15]=15s -> temporal_iou = 1/3
    system_events = [
        SystemMotionEvent(
            start_time=_T0 + timedelta(seconds=5), end_time=_T0 + timedelta(seconds=15)
        )
    ]
    strict = match_motion_events(ground_truth, system_events, overlap_threshold=0.5)
    lenient = match_motion_events(ground_truth, system_events, overlap_threshold=0.3)
    assert strict.counts.tp == 0
    assert lenient.counts.tp == 1
