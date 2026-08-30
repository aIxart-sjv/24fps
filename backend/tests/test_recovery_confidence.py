"""Tests for generic recovery-confidence scoring (app/recovery/confidence.py), Phase 10."""

from __future__ import annotations

import pytest

from app.recovery.confidence import ConfidenceFactor, compute_confidence


def test_confidence_is_none_when_no_factor_could_be_measured():
    result = compute_confidence(
        [ConfidenceFactor(name="a", weight=1.0, value=None, basis="not measurable")]
    )
    assert result.confidence is None
    assert result.basis == []


def test_confidence_excludes_unmeasured_factors_from_the_average():
    result = compute_confidence(
        [
            ConfidenceFactor(name="a", weight=1.0, value=1.0, basis="a ok"),
            ConfidenceFactor(name="b", weight=5.0, value=None, basis="b not measurable"),
        ]
    )
    assert result.confidence == pytest.approx(1.0)
    assert result.basis == ["a ok"]


def test_confidence_is_a_correct_weighted_average():
    result = compute_confidence(
        [
            ConfidenceFactor(name="a", weight=2.0, value=1.0, basis="a"),
            ConfidenceFactor(name="b", weight=1.0, value=0.0, basis="b"),
        ]
    )
    assert result.confidence == pytest.approx(2.0 / 3.0)


def test_confidence_rejects_negative_weight():
    with pytest.raises(ValueError, match="weight"):
        compute_confidence([ConfidenceFactor(name="a", weight=-1.0, value=1.0, basis="x")])


def test_confidence_rejects_out_of_range_value():
    with pytest.raises(ValueError, match="outside"):
        compute_confidence([ConfidenceFactor(name="a", weight=1.0, value=1.5, basis="x")])


def test_confidence_with_no_factors_at_all_is_none():
    result = compute_confidence([])
    assert result.confidence is None
    assert result.basis == []
