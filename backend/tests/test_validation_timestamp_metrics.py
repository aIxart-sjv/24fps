"""Tests for app/validation/timestamp_metrics.py (Phase 14) -- timeline
validation: timestamp error, ordering correctness, missing timestamps.
Never recomputes normalization -- only compares already-known values."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.validation.timestamp_metrics import compare_timestamp, evaluate_ordering

_T0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)


def test_exact_timestamp_has_zero_error() -> None:
    comparison = compare_timestamp(_T0, _T0)
    assert comparison.error_seconds == 0.0


def test_known_small_offset() -> None:
    comparison = compare_timestamp(_T0, _T0 + timedelta(milliseconds=180))
    assert comparison.error_seconds == pytest.approx(0.18)


def test_known_large_offset() -> None:
    comparison = compare_timestamp(_T0, _T0 + timedelta(hours=1))
    assert comparison.error_seconds == pytest.approx(3600.0)


def test_negative_offset_when_actual_is_earlier() -> None:
    comparison = compare_timestamp(_T0, _T0 - timedelta(seconds=5))
    assert comparison.error_seconds == pytest.approx(-5.0)


def test_missing_expected_or_actual_yields_no_fabricated_error() -> None:
    assert compare_timestamp(None, _T0).error_seconds is None
    assert compare_timestamp(_T0, None).error_seconds is None
    assert compare_timestamp(None, None).error_seconds is None


def test_correct_ordering() -> None:
    order = ["A", "B", "C"]
    actual = {"A": _T0, "B": _T0 + timedelta(seconds=7), "C": _T0 + timedelta(seconds=19)}
    result = evaluate_ordering(order, actual)
    assert result.correct is True
    assert result.actual_order == order


def test_incorrect_ordering() -> None:
    order = ["A", "B", "C"]
    actual = {"A": _T0 + timedelta(seconds=19), "B": _T0 + timedelta(seconds=7), "C": _T0}
    result = evaluate_ordering(order, actual)
    assert result.correct is False
    assert result.actual_order == ["C", "B", "A"]


def test_missing_timestamps_leave_ordering_undetermined_not_fabricated() -> None:
    order = ["A", "B", "C"]
    actual = {"A": _T0, "B": _T0 + timedelta(seconds=7)}  # C missing
    result = evaluate_ordering(order, actual)
    assert result.correct is None
    assert result.actual_order is None
    assert result.missing_identifiers == ["C"]


def test_none_valued_timestamp_is_also_treated_as_missing() -> None:
    order = ["A", "B"]
    actual = {"A": _T0, "B": None}
    result = evaluate_ordering(order, actual)
    assert result.correct is None
    assert result.missing_identifiers == ["B"]
