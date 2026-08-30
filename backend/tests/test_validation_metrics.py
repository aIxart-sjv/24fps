"""Tests for app/validation/metrics.py (Phase 14) -- TP/FP/FN/precision/
recall/F1, exact values, explicit undefined handling."""

from __future__ import annotations

import pytest

from app.validation.metrics import ClassificationCounts, f1, precision, recall


def test_classification_counts_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="tp must be >= 0"):
        ClassificationCounts(tp=-1, fp=0, fn=0)
    with pytest.raises(ValueError, match="fp must be >= 0"):
        ClassificationCounts(tp=0, fp=-1, fn=0)
    with pytest.raises(ValueError, match="fn must be >= 0"):
        ClassificationCounts(tp=0, fp=0, fn=-1)


def test_perfect_result() -> None:
    counts = ClassificationCounts(tp=10, fp=0, fn=0)
    assert precision(counts) == 1.0
    assert recall(counts) == 1.0
    assert f1(counts) == 1.0


def test_completely_wrong_result() -> None:
    counts = ClassificationCounts(tp=0, fp=5, fn=5)
    assert precision(counts) == 0.0
    assert recall(counts) == 0.0
    # precision=recall=0.0 makes F1 a genuine 0/0 -- explicitly undefined,
    # not silently reported as 0.0.
    assert f1(counts) is None


def test_mixed_result_exact_values() -> None:
    # TP=6, FP=4, FN=2 -> precision=0.6, recall=0.75, f1=2*0.6*0.75/1.35
    counts = ClassificationCounts(tp=6, fp=4, fn=2)
    assert precision(counts) == pytest.approx(0.6)
    assert recall(counts) == pytest.approx(0.75)
    assert f1(counts) == pytest.approx(2 * 0.6 * 0.75 / (0.6 + 0.75))


def test_zero_positive_predictions_precision_is_undefined() -> None:
    counts = ClassificationCounts(tp=0, fp=0, fn=3)
    assert precision(counts) is None
    assert recall(counts) == 0.0
    assert f1(counts) is None


def test_zero_ground_truth_recall_is_undefined() -> None:
    counts = ClassificationCounts(tp=0, fp=3, fn=0)
    assert recall(counts) is None
    assert precision(counts) == 0.0
    assert f1(counts) is None


def test_zero_everything_is_fully_undefined() -> None:
    counts = ClassificationCounts(tp=0, fp=0, fn=0)
    assert precision(counts) is None
    assert recall(counts) is None
    assert f1(counts) is None


def test_never_returns_nan_or_inf() -> None:
    import math

    for tp, fp, fn in [(0, 0, 0), (0, 0, 5), (0, 5, 0), (5, 0, 0)]:
        counts = ClassificationCounts(tp=tp, fp=fp, fn=fn)
        for value in (precision(counts), recall(counts), f1(counts)):
            assert value is None or (not math.isnan(value) and not math.isinf(value))
