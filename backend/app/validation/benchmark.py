"""
Validation-run packaging utilities (Phase 14, task Phase 14 scope sections
17-18, 31).

Shared, pure vocabulary every type-specific metric module's output gets
converted into before persistence: `MetricRecord` is the flat
name/value/numerator/denominator shape `app.core.validation_manager.
ValidationManager` writes as `ValidationMetric` rows.
`app.core.validation_manager` is the DB-aware layer that loads ground
truth/system output, calls the right `app.validation.*_metrics` module
directly, and uses `metrics_from_counts`/`structural_check_metrics` here
to package the result -- nothing in this module touches the database or
HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.validation.metrics import ClassificationCounts, f1, precision, recall

__all__ = [
    "MetricRecord",
    "ValidationRunResult",
    "ValidationType",
    "metrics_from_counts",
    "structural_check_metrics",
]


class ValidationType(str, Enum):
    """The validation types this phase implements (task Phase 14 scope
    sections 6-15)."""

    OBJECT_DETECTION = "object_detection"
    FACE_DETECTION = "face_detection"
    MOTION = "motion"
    TRACKING = "tracking"
    TIMELINE = "timeline"
    CORRELATION = "correlation"
    RECOVERY = "recovery"
    VENDOR_PARSER = "vendor_parser"


@dataclass(frozen=True)
class MetricRecord:
    """One named metric produced by a validation run -- the flat shape
    persisted as one `ValidationMetric` row.

    `value` is `None` (never `NaN`/`inf`) when the metric is explicitly
    undefined (e.g. precision with no positive predictions) -- task
    Phase 14 scope section 17: "Do not return misleading NaN/infinity
    values without a defined status."
    """

    name: str
    value: float | None
    numerator: float | None = None
    denominator: float | None = None
    threshold: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ValidationRunResult:
    """The full outcome of one validation run's metric computation."""

    validation_type: str
    metrics: list[MetricRecord]
    warnings: list[str] = field(default_factory=list)
    processing_time_seconds: float = 0.0


def metrics_from_counts(counts: ClassificationCounts, *, prefix: str = "") -> list[MetricRecord]:
    """Build the standard TP/FP/FN/precision/recall/F1 metric records.

    Args:
        counts: The classification counts to summarize.
        prefix: Optional metric-name prefix (e.g. `"object_detection."`).

    Returns:
        6 `MetricRecord`s: `{prefix}true_positives`,
        `{prefix}false_positives`, `{prefix}false_negatives`,
        `{prefix}precision`, `{prefix}recall`, `{prefix}f1`.
    """
    p = precision(counts)
    r = recall(counts)
    return [
        MetricRecord(name=f"{prefix}true_positives", value=float(counts.tp)),
        MetricRecord(name=f"{prefix}false_positives", value=float(counts.fp)),
        MetricRecord(name=f"{prefix}false_negatives", value=float(counts.fn)),
        MetricRecord(
            name=f"{prefix}precision",
            value=p,
            numerator=float(counts.tp),
            denominator=float(counts.tp + counts.fp),
        ),
        MetricRecord(
            name=f"{prefix}recall",
            value=r,
            numerator=float(counts.tp),
            denominator=float(counts.tp + counts.fn),
        ),
        MetricRecord(name=f"{prefix}f1", value=f1(counts)),
    ]


def structural_check_metrics(checks: dict[str, bool], *, prefix: str = "") -> list[MetricRecord]:
    """Build pass/fail metric records for simple boolean structural checks.

    Task Phase 14 scope section 15 (vendor/parser validation): "file
    recognized", "expected record structure", etc. are single yes/no
    facts about one real evidence item, not a TP/FP/FN classification
    problem over a set of predictions.

    Args:
        checks: `{check_name: passed}`.
        prefix: Optional metric-name prefix.

    Returns:
        One `MetricRecord` per check, `value=1.0` if passed else `0.0`.
    """
    return [
        MetricRecord(name=f"{prefix}{name}", value=1.0 if passed else 0.0)
        for name, passed in checks.items()
    ]
