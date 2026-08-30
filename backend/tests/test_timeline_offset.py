"""Tests for generic clock-offset calculation (app/timeline/offset.py), Phase 11."""

from __future__ import annotations

import datetime

import pytest

from app.timeline.offset import NaiveTimestampError, compute_offset

UTC = datetime.UTC


def test_zero_offset():
    t = datetime.datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC)
    result = compute_offset(t, t)
    assert result.offset_seconds == 0.0
    assert result.recorder_is_ahead is False


def test_positive_offset_recorder_behind():
    recorder = datetime.datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC)
    reference = datetime.datetime(2026, 8, 28, 16, 27, 38, tzinfo=UTC)
    result = compute_offset(recorder, reference)
    assert result.offset_seconds == pytest.approx(
        458.0
    )  # 7m38s, matching Master Spec §26's example
    assert result.recorder_is_ahead is False


def test_negative_offset_recorder_ahead():
    recorder = datetime.datetime(2026, 8, 28, 16, 20, 10, tzinfo=UTC)
    reference = datetime.datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC)
    result = compute_offset(recorder, reference)
    assert result.offset_seconds == pytest.approx(-10.0)
    assert result.recorder_is_ahead is True


def test_exact_reference_pair_five_seconds():
    recorder = datetime.datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC)
    reference = datetime.datetime(2026, 8, 28, 16, 20, 5, tzinfo=UTC)
    result = compute_offset(recorder, reference)
    assert result.offset_seconds == 5.0


def test_midnight_rollover():
    recorder = datetime.datetime(2026, 8, 28, 23, 59, 55, tzinfo=UTC)
    reference = datetime.datetime(2026, 8, 29, 0, 0, 5, tzinfo=UTC)
    result = compute_offset(recorder, reference)
    assert result.offset_seconds == pytest.approx(10.0)


def test_date_rollover_recorder_ahead_of_reference_by_a_day():
    recorder = datetime.datetime(2026, 8, 29, 0, 0, 5, tzinfo=UTC)
    reference = datetime.datetime(2026, 8, 28, 23, 59, 55, tzinfo=UTC)
    result = compute_offset(recorder, reference)
    assert result.offset_seconds == pytest.approx(-10.0)


def test_month_rollover():
    recorder = datetime.datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC)
    reference = datetime.datetime(2026, 9, 1, 0, 0, 1, tzinfo=UTC)
    result = compute_offset(recorder, reference)
    assert result.offset_seconds == pytest.approx(2.0)


def test_year_rollover():
    recorder = datetime.datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)
    reference = datetime.datetime(2027, 1, 1, 0, 0, 4, tzinfo=UTC)
    result = compute_offset(recorder, reference)
    assert result.offset_seconds == pytest.approx(5.0)


def test_offset_across_different_timezones_representing_the_same_instant():
    recorder = datetime.datetime(
        2026, 8, 28, 21, 50, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    )
    reference = datetime.datetime(2026, 8, 28, 16, 20, 5, tzinfo=UTC)
    result = compute_offset(recorder, reference)
    assert result.offset_seconds == pytest.approx(5.0)


def test_rejects_naive_recorder_time():
    aware = datetime.datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC)
    naive = datetime.datetime(2026, 8, 28, 16, 20, 0)
    with pytest.raises(NaiveTimestampError, match="recorder_time"):
        compute_offset(naive, aware)


def test_rejects_naive_reference_time():
    aware = datetime.datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC)
    naive = datetime.datetime(2026, 8, 28, 16, 20, 0)
    with pytest.raises(NaiveTimestampError, match="reference_time"):
        compute_offset(aware, naive)
