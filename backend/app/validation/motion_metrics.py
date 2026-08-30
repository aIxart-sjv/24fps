"""
Motion-event validation (Phase 14, Master Specification Section 34;
task Phase 14 scope section 10).

Matches ground-truth motion intervals against the system's actual
persisted `MotionEvent` rows using temporal overlap ("temporal IoU": the
same intersection-over-union principle `app.validation.frame_metrics`
uses for bounding boxes, applied to `[start, end]` time intervals instead)
against a documented, configurable threshold. Motion validation measures
"was motion detected when and where expected" -- it never classifies
what moved (that is object detection's job, validated separately).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.validation.ground_truth import GroundTruthMotionEvent
from app.validation.metrics import ClassificationCounts

__all__ = [
    "DEFAULT_TEMPORAL_OVERLAP_THRESHOLD",
    "MotionMatch",
    "MotionMatchResult",
    "SystemMotionEvent",
    "match_motion_events",
    "temporal_iou",
]

#: No document pins an exact overlap threshold; 0.3 is deliberately more
#: lenient than `frame_metrics.DEFAULT_IOU_THRESHOLD` (0.5) because motion
#: start/end boundaries are inherently fuzzier than a bounding box edge --
#: always overridable, always recorded on the result.
DEFAULT_TEMPORAL_OVERLAP_THRESHOLD = 0.3


@dataclass(frozen=True)
class SystemMotionEvent:
    """One system-produced motion event, in absolute time (as persisted
    on `app.models.ai_result.MotionEvent.start_time`/`end_time`)."""

    start_time: datetime
    end_time: datetime


def temporal_iou(
    a: GroundTruthMotionEvent | SystemMotionEvent, b: GroundTruthMotionEvent | SystemMotionEvent
) -> float:
    """Intersection-over-union of two `[start, end]` time intervals.

    Args:
        a: The first interval.
        b: The second interval.

    Returns:
        A value in `[0.0, 1.0]`. `0.0` for non-overlapping or
        degenerate intervals.
    """
    intersection_start = max(a.start_time, b.start_time)
    intersection_end = min(a.end_time, b.end_time)
    intersection = max((intersection_end - intersection_start).total_seconds(), 0.0)

    union_start = min(a.start_time, b.start_time)
    union_end = max(a.end_time, b.end_time)
    union = (union_end - union_start).total_seconds()

    if union <= 0:
        return 0.0
    return intersection / union


@dataclass(frozen=True)
class MotionMatch:
    """One matched (ground-truth, system) motion-event pair."""

    ground_truth: GroundTruthMotionEvent
    system_event: SystemMotionEvent
    overlap: float
    start_error_seconds: float
    end_error_seconds: float


@dataclass(frozen=True)
class MotionMatchResult:
    """The full outcome of matching system motion events against ground truth."""

    counts: ClassificationCounts
    matches: list[MotionMatch]
    unmatched_ground_truth: list[GroundTruthMotionEvent]
    unmatched_system_events: list[SystemMotionEvent]
    overlap_threshold: float


def match_motion_events(
    ground_truth: list[GroundTruthMotionEvent],
    system_events: list[SystemMotionEvent],
    *,
    overlap_threshold: float = DEFAULT_TEMPORAL_OVERLAP_THRESHOLD,
) -> MotionMatchResult:
    """Match system motion events against ground truth via greedy best-overlap assignment.

    Args:
        ground_truth: The independently-known expected motion intervals.
        system_events: The system's actual persisted motion events.
        overlap_threshold: Minimum temporal IoU for a candidate pair to
            be eligible. Always recorded as a validation parameter.

    Returns:
        A `MotionMatchResult`: TP = matched pairs (with timing error
        computed only for matches), FP = unmatched system events
        (false motion), FN = unmatched ground truth (missed motion).
    """
    candidates: list[tuple[float, int, int]] = []
    for gt_index, gt in enumerate(ground_truth):
        for event_index, event in enumerate(system_events):
            overlap = temporal_iou(gt, event)
            if overlap >= overlap_threshold:
                candidates.append((overlap, gt_index, event_index))

    candidates.sort(key=lambda candidate: candidate[0], reverse=True)

    matched_gt: set[int] = set()
    matched_events: set[int] = set()
    matches: list[MotionMatch] = []
    for overlap, gt_index, event_index in candidates:
        if gt_index in matched_gt or event_index in matched_events:
            continue
        matched_gt.add(gt_index)
        matched_events.add(event_index)
        gt = ground_truth[gt_index]
        event = system_events[event_index]
        matches.append(
            MotionMatch(
                ground_truth=gt,
                system_event=event,
                overlap=overlap,
                start_error_seconds=(event.start_time - gt.start_time).total_seconds(),
                end_error_seconds=(event.end_time - gt.end_time).total_seconds(),
            )
        )

    unmatched_ground_truth = [gt for i, gt in enumerate(ground_truth) if i not in matched_gt]
    unmatched_system_events = [e for i, e in enumerate(system_events) if i not in matched_events]

    counts = ClassificationCounts(
        tp=len(matches), fp=len(unmatched_system_events), fn=len(unmatched_ground_truth)
    )
    return MotionMatchResult(
        counts=counts,
        matches=matches,
        unmatched_ground_truth=unmatched_ground_truth,
        unmatched_system_events=unmatched_system_events,
        overlap_threshold=overlap_threshold,
    )
