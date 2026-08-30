"""Tests for generic counter-continuity math (app/recovery/continuity.py), Phase 10."""

from __future__ import annotations

import pytest

from app.recovery.continuity import measure_counter_continuity


def test_continuity_fully_continuous_sequence():
    result = measure_counter_continuity([100, 101, 102, 103])
    assert result.total_steps == 3
    assert result.continuous_steps == 3
    assert result.gaps == []
    assert result.continuity_fraction == 1.0


def test_continuity_detects_a_single_gap():
    result = measure_counter_continuity([1, 2, 3, 5, 6])
    assert result.total_steps == 4
    assert result.continuous_steps == 3
    assert result.gaps == [(3, 5)]
    assert result.continuity_fraction == 0.75


def test_continuity_detects_multiple_gaps():
    result = measure_counter_continuity([1, 5, 6, 10])
    assert result.gaps == [(1, 5), (6, 10)]
    # 3 steps total: 1->5 (gap), 5->6 (continuous), 6->10 (gap) = 1/3 continuous.
    assert result.continuity_fraction == pytest.approx(1 / 3)


def test_continuity_with_fewer_than_two_counters_is_undefined():
    assert measure_counter_continuity([]).continuity_fraction is None
    assert measure_counter_continuity([42]).continuity_fraction is None


def test_continuity_treats_a_decrease_as_a_gap_not_a_crash():
    result = measure_counter_continuity([5, 4, 3])
    assert result.continuous_steps == 0
    assert result.gaps == [(5, 4), (4, 3)]
