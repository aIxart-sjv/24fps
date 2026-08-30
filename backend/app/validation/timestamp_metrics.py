"""
Timeline/timestamp validation (Phase 14, task Phase 14 scope section 12).

Uses Phase 11's normalized timestamps exactly as computed --
`app.core.timestamp_manager`/`app.timeline.normalization` are read from,
never touched or reimplemented. This module only measures the difference
between an independently-known expected timestamp and the system's
actual value, and whether a sequence of actual timestamps preserves an
expected chronological order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

__all__ = ["OrderingResult", "TimestampComparison", "compare_timestamp", "evaluate_ordering"]


@dataclass(frozen=True)
class TimestampComparison:
    """One expected-vs-actual timestamp comparison.

    `error_seconds` is `None` (never fabricated) when either side is
    missing -- e.g. a recording with no normalized start.
    """

    expected: datetime | None
    actual: datetime | None
    error_seconds: float | None


def compare_timestamp(expected: datetime | None, actual: datetime | None) -> TimestampComparison:
    """Compute the signed error (`actual - expected`, in seconds) between
    an expected and an actual timestamp.

    Args:
        expected: The independently-known expected timestamp.
        actual: The system's actual (normalized) timestamp.

    Returns:
        A `TimestampComparison`. `error_seconds` is `None` if either
        input is `None`.
    """
    if expected is None or actual is None:
        return TimestampComparison(expected=expected, actual=actual, error_seconds=None)
    return TimestampComparison(
        expected=expected, actual=actual, error_seconds=(actual - expected).total_seconds()
    )


@dataclass(frozen=True)
class OrderingResult:
    """Whether a sequence of actual timestamps preserves an expected
    chronological order.

    `correct` is `None` (undetermined, not silently `True`/`False`) when
    one or more identifiers in `expected_order` had no usable actual
    timestamp.
    """

    expected_order: list[str]
    actual_order: list[str] | None
    correct: bool | None
    missing_identifiers: list[str] = field(default_factory=list)


def evaluate_ordering(
    expected_order: list[str], actual_timestamps: dict[str, datetime | None]
) -> OrderingResult:
    """Evaluate whether `actual_timestamps` preserves `expected_order`.

    Args:
        expected_order: Event identifiers, in their expected
            chronological order.
        actual_timestamps: `{identifier: actual_timestamp}` for every
            identifier in `expected_order`. An identifier missing from
            this mapping, or mapped to `None`, is reported explicitly
            rather than silently excluded.

    Returns:
        An `OrderingResult`. If any expected identifier lacks a usable
        actual timestamp, `correct` is `None` and those identifiers are
        listed in `missing_identifiers` -- ordering is never guessed from
        partial data.
    """
    missing = [
        identifier for identifier in expected_order if actual_timestamps.get(identifier) is None
    ]
    if missing:
        return OrderingResult(
            expected_order=expected_order,
            actual_order=None,
            correct=None,
            missing_identifiers=missing,
        )

    actual_order = sorted(expected_order, key=lambda identifier: actual_timestamps[identifier])  # type: ignore[arg-type,return-value]
    return OrderingResult(
        expected_order=expected_order,
        actual_order=actual_order,
        correct=actual_order == expected_order,
    )
