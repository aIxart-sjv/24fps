"""
Cross-camera correlation validation (Phase 14, Master Specification
Section 29; task Phase 14 scope section 13).

Validates SEQUENCE RECONSTRUCTION -- whether the system's actual,
already-persisted Phase 12 correlation output reproduces an independently
-known expected event sequence (e.g. the documented A -> B -> C scenario:
Camera A/entrance -> Camera B/lobby -> Camera C/corridor). This never
reimplements or re-runs correlation (`app.timeline.correlation` stays
untouched) -- both sides of the comparison here are plain, already-
computed data the caller supplies.

This module explicitly distinguishes "correctly correlated events" from
"confirmed same person": nothing here produces or consumes an identity
claim. A correctly-matched sequence means the system grouped the expected
events together in the expected order -- not that a person was identified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.validation.ground_truth import GroundTruthSequence
from app.validation.metrics import ClassificationCounts

__all__ = [
    "DEFAULT_TIME_TOLERANCE_SECONDS",
    "SequenceMatch",
    "SequenceMatchResult",
    "SystemSequenceEvent",
    "SystemSequenceGroup",
    "match_sequences",
    "sequence_matches",
]

#: No document pins an exact matching tolerance; this mirrors
#: `app.timeline.correlation.DEFAULT_MAX_GAP_SECONDS` (120s) since the
#: expected sequence's own timestamps and the system's persisted
#: normalized timestamps originate from the same correlation run --
#: always overridable, always recorded on the result.
DEFAULT_TIME_TOLERANCE_SECONDS = 5.0


@dataclass(frozen=True)
class SystemSequenceEvent:
    """One event within a system-produced correlation group (read from
    the actual persisted Phase 12 `correlated_event` `TimelineEvent`
    grouping -- never re-derived)."""

    camera_id: str
    timestamp: datetime


@dataclass(frozen=True)
class SystemSequenceGroup:
    """One system-produced correlation candidate group."""

    correlation_id: str
    events: list[SystemSequenceEvent] = field(default_factory=list)


def sequence_matches(
    ground_truth: GroundTruthSequence,
    system_group: SystemSequenceGroup,
    *,
    time_tolerance_seconds: float = DEFAULT_TIME_TOLERANCE_SECONDS,
) -> bool:
    """Whether one system group correctly reproduces one expected sequence.

    Requires the same number of events, the same camera order, and each
    corresponding pair's timestamps within `time_tolerance_seconds` --
    an incomplete group (fewer events) or an out-of-order/wrong-camera
    group never matches.

    Args:
        ground_truth: The expected ordered sequence.
        system_group: One system-produced correlation group.
        time_tolerance_seconds: Maximum allowed timestamp difference per
            matched event pair.

    Returns:
        `True` if `system_group` reproduces `ground_truth` exactly (in
        order, within tolerance); `False` otherwise.
    """
    gt_events = ground_truth.events
    sys_events = sorted(system_group.events, key=lambda event: event.timestamp)
    if len(gt_events) != len(sys_events):
        return False
    for expected, actual in zip(gt_events, sys_events, strict=True):
        if expected.camera_id != actual.camera_id:
            return False
        if abs((expected.timestamp - actual.timestamp).total_seconds()) > time_tolerance_seconds:
            return False
    return True


@dataclass(frozen=True)
class SequenceMatch:
    """One matched (ground-truth, system-group) sequence pair."""

    ground_truth: GroundTruthSequence
    system_group: SystemSequenceGroup


@dataclass(frozen=True)
class SequenceMatchResult:
    """The full outcome of matching system correlation groups against
    expected sequences."""

    counts: ClassificationCounts
    matches: list[SequenceMatch]
    unmatched_ground_truth: list[GroundTruthSequence]
    unmatched_system_groups: list[SystemSequenceGroup]
    time_tolerance_seconds: float


def match_sequences(
    ground_truth: list[GroundTruthSequence],
    system_groups: list[SystemSequenceGroup],
    *,
    time_tolerance_seconds: float = DEFAULT_TIME_TOLERANCE_SECONDS,
) -> SequenceMatchResult:
    """Match system correlation groups against expected sequences.

    Args:
        ground_truth: The independently-known expected sequences (e.g.
            one `GroundTruthSequence` for the A -> B -> C scenario).
        system_groups: The system's actual, already-persisted correlation
            candidate groups for the same case.
        time_tolerance_seconds: See `sequence_matches`.

    Returns:
        A `SequenceMatchResult`: TP = an expected sequence was correctly
        reconstructed, FN = an expected sequence was not found (missed
        or reconstructed incorrectly/incompletely), FP = a system group
        that does not correspond to any expected sequence.
    """
    matched_gt: set[int] = set()
    matched_groups: set[int] = set()
    matches: list[SequenceMatch] = []

    for gt_index, gt in enumerate(ground_truth):
        for group_index, group in enumerate(system_groups):
            if group_index in matched_groups:
                continue
            if sequence_matches(gt, group, time_tolerance_seconds=time_tolerance_seconds):
                matched_gt.add(gt_index)
                matched_groups.add(group_index)
                matches.append(SequenceMatch(ground_truth=gt, system_group=group))
                break

    unmatched_ground_truth = [gt for i, gt in enumerate(ground_truth) if i not in matched_gt]
    unmatched_system_groups = [
        group for i, group in enumerate(system_groups) if i not in matched_groups
    ]

    counts = ClassificationCounts(
        tp=len(matches), fp=len(unmatched_system_groups), fn=len(unmatched_ground_truth)
    )
    return SequenceMatchResult(
        counts=counts,
        matches=matches,
        unmatched_ground_truth=unmatched_ground_truth,
        unmatched_system_groups=unmatched_system_groups,
        time_tolerance_seconds=time_tolerance_seconds,
    )
