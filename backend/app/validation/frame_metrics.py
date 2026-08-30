"""
Object/face detection validation (Phase 14, Master Specification Section
36; task Phase 14 scope sections 6-9).

Validates DETECTION only. For face detection this measures whether a face
bounding box was found, never whether an identity was recognized (Master
Specification Section 33: face recognition is not part of the required
core) -- nothing in this module reads or produces an identity-shaped
value.

Bounding-box matching uses intersection-over-union (IoU) against a
documented, configurable threshold -- never an undocumented rule. Class
agreement is required by default: a `"car"` prediction against a
`"truck"` ground-truth box is never counted as a true positive for
either class (task Phase 14 scope section 8).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.types import BoundingBox, Detection
from app.validation.ground_truth import GroundTruthDetection
from app.validation.metrics import ClassificationCounts

__all__ = [
    "DEFAULT_IOU_THRESHOLD",
    "DetectionMatch",
    "DetectionMatchResult",
    "iou",
    "match_detections",
]

#: No document pins an exact IoU threshold for this project; 0.5 is the
#: conventional default used across object-detection benchmarking
#: literature (e.g. PASCAL VOC) and is always overridable per call -- the
#: effective value is always recorded on `DetectionMatchResult`.
DEFAULT_IOU_THRESHOLD = 0.5


def iou(a: BoundingBox, b: BoundingBox) -> float:
    """Intersection-over-union of two axis-aligned bounding boxes.

    Args:
        a: The first bounding box.
        b: The second bounding box.

    Returns:
        A value in `[0.0, 1.0]`. `0.0` for non-overlapping or
        degenerate (zero-or-negative-area) boxes -- never divides by
        zero.
    """
    x_min = max(a.x_min, b.x_min)
    y_min = max(a.y_min, b.y_min)
    x_max = min(a.x_max, b.x_max)
    y_max = min(a.y_max, b.y_max)

    intersection_area = max(0.0, x_max - x_min) * max(0.0, y_max - y_min)

    area_a = max(0.0, a.x_max - a.x_min) * max(0.0, a.y_max - a.y_min)
    area_b = max(0.0, b.x_max - b.x_min) * max(0.0, b.y_max - b.y_min)
    union_area = area_a + area_b - intersection_area

    if union_area <= 0:
        return 0.0
    return intersection_area / union_area


@dataclass(frozen=True)
class DetectionMatch:
    """One matched (ground-truth, prediction) pair."""

    ground_truth: GroundTruthDetection
    prediction: Detection
    iou: float


@dataclass(frozen=True)
class DetectionMatchResult:
    """The full outcome of matching predictions against ground truth."""

    counts: ClassificationCounts
    matches: list[DetectionMatch]
    unmatched_ground_truth: list[GroundTruthDetection]
    unmatched_predictions: list[Detection]
    iou_threshold: float
    require_class_match: bool
    require_frame_match: bool


def match_detections(
    ground_truth: list[GroundTruthDetection],
    predictions: list[Detection],
    *,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    require_class_match: bool = True,
    require_frame_match: bool = True,
) -> DetectionMatchResult:
    """Match predicted detections against ground truth via greedy best-IoU assignment.

    Each ground-truth box matches at most one prediction and vice versa
    -- duplicate predictions covering the same real object are never
    counted as multiple true positives. Matching proceeds greedily in
    descending IoU order over every class-eligible, frame-eligible,
    threshold-eligible pair: a documented, deterministic rule, not an
    arbitrary one.

    Args:
        ground_truth: The independently-known expected detections.
        predictions: The system's actual detections (e.g. loaded from
            persisted `AIResult` rows and converted to
            `app.ai.types.Detection`).
        iou_threshold: Minimum IoU for a candidate pair to be eligible.
            Always recorded by the caller as a validation parameter.
        require_class_match: When `True` (the default), a pair is only
            eligible if `class_name` agrees exactly.
        require_frame_match: When `True` (the default), a pair is only
            eligible if both sides name the same `frame_number` -- a
            ground-truth box for frame 5 must never match a prediction
            from frame 50 just because the coordinates happen to
            overlap. Only enforced when the ground-truth entry actually
            has a `frame_number` (`None` means "not frame-specific," so
            frame is not used as a filter for that entry).

    Returns:
        A `DetectionMatchResult`: TP = matched pairs, FP = unmatched
        predictions, FN = unmatched ground truth.
    """
    candidates: list[tuple[float, int, int]] = []
    for gt_index, gt in enumerate(ground_truth):
        for pred_index, pred in enumerate(predictions):
            if require_class_match and gt.class_name != pred.class_name:
                continue
            if (
                require_frame_match
                and gt.frame_number is not None
                and gt.frame_number != pred.frame_number
            ):
                continue
            score = iou(gt.bbox, pred.bbox)
            if score >= iou_threshold:
                candidates.append((score, gt_index, pred_index))

    candidates.sort(key=lambda candidate: candidate[0], reverse=True)

    matched_gt: set[int] = set()
    matched_pred: set[int] = set()
    matches: list[DetectionMatch] = []
    for score, gt_index, pred_index in candidates:
        if gt_index in matched_gt or pred_index in matched_pred:
            continue
        matched_gt.add(gt_index)
        matched_pred.add(pred_index)
        matches.append(
            DetectionMatch(
                ground_truth=ground_truth[gt_index], prediction=predictions[pred_index], iou=score
            )
        )

    unmatched_ground_truth = [gt for i, gt in enumerate(ground_truth) if i not in matched_gt]
    unmatched_predictions = [p for i, p in enumerate(predictions) if i not in matched_pred]

    counts = ClassificationCounts(
        tp=len(matches), fp=len(unmatched_predictions), fn=len(unmatched_ground_truth)
    )
    return DetectionMatchResult(
        counts=counts,
        matches=matches,
        unmatched_ground_truth=unmatched_ground_truth,
        unmatched_predictions=unmatched_predictions,
        iou_threshold=iou_threshold,
        require_class_match=require_class_match,
        require_frame_match=require_frame_match,
    )
