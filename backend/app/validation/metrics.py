"""
Shared classification-metric primitives (Phase 14, Master Specification
Section 36 "Validation Engine").

Pure, dependency-free arithmetic used by every type-specific validation
module (`frame_metrics`, `motion_metrics`, `tracking_metrics`,
`correlation_metrics`) so precision/recall/F1 are defined exactly once,
the same way everywhere. Model confidence and validation accuracy are
different things: nothing in this module reads or depends on a detection's
`confidence` score -- a validation metric here answers "was this
prediction correct" against ground truth, never "how sure was the model."
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ClassificationCounts", "f1", "precision", "recall"]


@dataclass(frozen=True)
class ClassificationCounts:
    """True/false positive/negative counts for one validation comparison."""

    tp: int
    fp: int
    fn: int

    def __post_init__(self) -> None:
        for name, value in (("tp", self.tp), ("fp", self.fp), ("fn", self.fn)):
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")


def precision(counts: ClassificationCounts) -> float | None:
    """`TP / (TP + FP)`.

    Args:
        counts: The classification counts to compute precision from.

    Returns:
        The precision value, or `None` (explicitly undefined, never
        `NaN`/`inf`) when `TP + FP == 0` -- there were no positive
        predictions to be precise about.
    """
    denominator = counts.tp + counts.fp
    if denominator == 0:
        return None
    return counts.tp / denominator


def recall(counts: ClassificationCounts) -> float | None:
    """`TP / (TP + FN)`.

    Args:
        counts: The classification counts to compute recall from.

    Returns:
        The recall value, or `None` (explicitly undefined) when
        `TP + FN == 0` -- there was no ground truth to recall.
    """
    denominator = counts.tp + counts.fn
    if denominator == 0:
        return None
    return counts.tp / denominator


def f1(counts: ClassificationCounts) -> float | None:
    """`2 * Precision * Recall / (Precision + Recall)`.

    Args:
        counts: The classification counts to compute F1 from.

    Returns:
        The F1 value, or `None` (explicitly undefined) when precision or
        recall is itself undefined, or when both are `0.0` (their sum is
        the denominator here).
    """
    p = precision(counts)
    r = recall(counts)
    if p is None or r is None:
        return None
    if p + r == 0:
        return None
    return 2 * p * r / (p + r)
