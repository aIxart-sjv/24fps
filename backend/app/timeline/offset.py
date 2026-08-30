"""
Generic recorder/reference clock-offset calculation
(Master Specification Section 26/27).

Task Phase 11 scope, section 4/7: an offset may only be computed from a
recorder timestamp and reference timestamp that "correspond to the same
real-world instant or a precisely identifiable event" — this module never
decides *whether* a supplied pair is trustworthy (that judgment, and the
evidence behind it, belongs to the caller/examiner — see
`app.timeline.__init__.ReferencePair.reference_basis`); it only performs
the arithmetic once both timestamps are already timezone-aware, and
refuses to guess when given naive input.

Plain `datetime` subtraction already accounts for midnight/date/month/
year rollover correctly, because both operands are points on one
continuous timeline — no special-cased rollover logic is implemented or
needed here (task Phase 11 scope, section 16/23).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class NaiveTimestampError(ValueError):
    """Raised when offset calculation is attempted with a timezone-naive input."""


@dataclass(frozen=True)
class OffsetResult:
    """The result of comparing a recorder timestamp against a reference timestamp."""

    offset_seconds: float

    @property
    def recorder_is_ahead(self) -> bool:
        """Whether the recorder's clock reads later than the reference (negative offset)."""
        return self.offset_seconds < 0


def compute_offset(recorder_time: datetime, reference_time: datetime) -> OffsetResult:
    """Compute `reference_time - recorder_time` as a clock offset in seconds.

    Args:
        recorder_time: The recorder/device's own timezone-aware timestamp
            for a specific, identifiable instant.
        reference_time: An independently-sourced, timezone-aware
            timestamp for that same instant.

    Returns:
        An `OffsetResult`. Positive `offset_seconds` means the recorder's
        clock reads *earlier* than the reference (the recorder is
        "behind"); negative means the recorder is "ahead". Correct across
        midnight/month/year boundaries by construction — both inputs are
        absolute instants, not calendar fields.

    Raises:
        NaiveTimestampError: If either input is timezone-naive — offset
            calculation must never guess a timezone for either side.
    """
    if recorder_time.tzinfo is None:
        raise NaiveTimestampError(f"recorder_time {recorder_time!r} is timezone-naive")
    if reference_time.tzinfo is None:
        raise NaiveTimestampError(f"reference_time {reference_time!r} is timezone-naive")
    return OffsetResult(offset_seconds=(reference_time - recorder_time).total_seconds())
