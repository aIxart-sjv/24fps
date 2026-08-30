"""
Generic timestamp-candidate assembly (Master Specification Section 26/27).

Deliberately thin: classifying *which* of a vendor's fields is trustworthy
enough to even offer as a normalization candidate is vendor-specific
judgment (e.g. knowing that CP Plus's `Recording.start_original` is
always filename-derived, never the unvalidated binary counter) — that
judgment belongs in `app.core.timestamp_manager`, which is explicitly
allowed to be vendor-dispatch-aware (mirroring `RecordingManager`/
`RecoveryManager`). This module only defines the common shape a candidate
is assembled into, so every caller produces the same structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.timeline import TimestampSource


@dataclass(frozen=True)
class TimestampCandidate:
    """One original-timestamp candidate, with its declared source.

    `value` is `None` when the source is known to exist conceptually but
    has no usable value right now (e.g. a vendor binary timestamp whose
    meaning is unresolved) — carrying the source forward even without a
    value keeps the "why is this unknown" explanation available.
    """

    source: TimestampSource
    value: datetime | None
    note: str | None = None


def build_candidate(
    value: datetime | None, source: TimestampSource, *, note: str | None = None
) -> TimestampCandidate:
    """Assemble one `TimestampCandidate` from an already-extracted value and its source.

    Args:
        value: The timestamp value, or `None` if unavailable/unusable.
        source: The declared `TimestampSource` for `value`.
        note: Optional free-text context (e.g. why a value is `None`, or
            which evidence field it was read from).

    Returns:
        A `TimestampCandidate`.
    """
    return TimestampCandidate(source=source, value=value, note=note)
