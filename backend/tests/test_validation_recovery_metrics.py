"""Tests for app/validation/recovery_metrics.py (Phase 14) -- recovery
validation: expected-vs-actual comparison, never recomputing recovery
itself. Deleted-record recovery is kept explicitly separate/unvalidated
when no ground truth for a deletion scenario exists."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.validation.ground_truth import GroundTruthRecoverySegment
from app.validation.recovery_metrics import SystemRecoveryOutcome, compare_recovery

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_known_damaged_segment_frames_and_fragments_error() -> None:
    ground_truth = GroundTruthRecoverySegment(expected_frames=100, expected_fragments=1)
    system_outcome = SystemRecoveryOutcome(
        status="partial",
        actual_start=None,
        actual_end=None,
        actual_duration_ms=None,
        frames_recovered=95,
        fragments_found=1,
        fragments_used=1,
        recovery_rate=0.95,
        frame_continuity=0.98,
        actual_hash=None,
    )
    comparison = compare_recovery(ground_truth, system_outcome)
    assert comparison.frames_error == -5
    assert comparison.fragments_error == 0


def test_known_missing_segment_reports_full_frame_deficit() -> None:
    ground_truth = GroundTruthRecoverySegment(expected_frames=200)
    system_outcome = SystemRecoveryOutcome(
        status="no_recovery_found",
        actual_start=None,
        actual_end=None,
        actual_duration_ms=None,
        frames_recovered=0,
        fragments_found=0,
        fragments_used=0,
        recovery_rate=0.0,
        frame_continuity=None,
        actual_hash=None,
    )
    comparison = compare_recovery(ground_truth, system_outcome)
    assert comparison.frames_error == -200


def test_controlled_fragment_ordering_matches() -> None:
    ground_truth = GroundTruthRecoverySegment(expected_fragments=3)
    system_outcome = SystemRecoveryOutcome(
        status="recovered",
        actual_start=None,
        actual_end=None,
        actual_duration_ms=None,
        frames_recovered=None,
        fragments_found=3,
        fragments_used=3,
        recovery_rate=1.0,
        frame_continuity=1.0,
        actual_hash=None,
    )
    comparison = compare_recovery(ground_truth, system_outcome)
    assert comparison.fragments_error == 0


def test_start_end_and_duration_error() -> None:
    ground_truth = GroundTruthRecoverySegment(
        expected_start=_T0, expected_end=_T0 + timedelta(seconds=10), expected_duration_ms=10000
    )
    system_outcome = SystemRecoveryOutcome(
        status="recovered",
        actual_start=_T0 + timedelta(milliseconds=180),
        actual_end=_T0 + timedelta(seconds=10),
        actual_duration_ms=9820,
        frames_recovered=None,
        fragments_found=None,
        fragments_used=None,
        recovery_rate=None,
        frame_continuity=None,
        actual_hash=None,
    )
    comparison = compare_recovery(ground_truth, system_outcome)
    assert comparison.start_error_seconds == pytest.approx(0.18)
    assert comparison.end_error_seconds == pytest.approx(0.0)
    assert comparison.duration_error_ms == -180


def test_hash_match() -> None:
    ground_truth = GroundTruthRecoverySegment(expected_hash="abc123")
    matching = SystemRecoveryOutcome(
        status="recovered",
        actual_start=None,
        actual_end=None,
        actual_duration_ms=None,
        frames_recovered=None,
        fragments_found=None,
        fragments_used=None,
        recovery_rate=None,
        frame_continuity=None,
        actual_hash="abc123",
    )
    mismatching = SystemRecoveryOutcome(
        status="recovered",
        actual_start=None,
        actual_end=None,
        actual_duration_ms=None,
        frames_recovered=None,
        fragments_found=None,
        fragments_used=None,
        recovery_rate=None,
        frame_continuity=None,
        actual_hash="def456",
    )
    assert compare_recovery(ground_truth, matching).hash_matches is True
    assert compare_recovery(ground_truth, mismatching).hash_matches is False


def test_missing_values_never_fabricate_an_error() -> None:
    ground_truth = GroundTruthRecoverySegment()  # nothing known
    system_outcome = SystemRecoveryOutcome(
        status=None,
        actual_start=None,
        actual_end=None,
        actual_duration_ms=None,
        frames_recovered=None,
        fragments_found=None,
        fragments_used=None,
        recovery_rate=None,
        frame_continuity=None,
        actual_hash=None,
    )
    comparison = compare_recovery(ground_truth, system_outcome)
    assert comparison.start_error_seconds is None
    assert comparison.end_error_seconds is None
    assert comparison.duration_error_ms is None
    assert comparison.frames_error is None
    assert comparison.fragments_error is None
    assert comparison.hash_matches is None
