"""Tests for app/validation/frame_metrics.py (Phase 14) -- object/face
detection validation: IoU, class matching, frame matching, configurable
threshold. Face detection reuses the exact same matcher -- covered here
too, with an explicit check that no identity field exists anywhere."""

from __future__ import annotations

import dataclasses

from app.ai.types import BoundingBox, Detection
from app.validation.frame_metrics import iou, match_detections
from app.validation.ground_truth import GroundTruthDetection


def _det(class_name: str, box: tuple[float, float, float, float], *, frame: int = 0) -> Detection:
    x1, y1, x2, y2 = box
    return Detection(
        class_name=class_name,
        confidence=0.9,
        bbox=BoundingBox(x1, y1, x2, y2),
        frame_number=frame,
        timestamp_seconds=0.0,
    )


def _gt(
    class_name: str, box: tuple[float, float, float, float], *, frame: int = 0
) -> GroundTruthDetection:
    x1, y1, x2, y2 = box
    return GroundTruthDetection(
        class_name=class_name, bbox=BoundingBox(x1, y1, x2, y2), frame_number=frame
    )


# --- IoU -------------------------------------------------------------


def test_iou_identical_boxes_is_one() -> None:
    box = BoundingBox(0, 0, 10, 10)
    assert iou(box, box) == 1.0


def test_iou_non_overlapping_boxes_is_zero() -> None:
    a = BoundingBox(0, 0, 10, 10)
    b = BoundingBox(20, 20, 30, 30)
    assert iou(a, b) == 0.0


def test_iou_known_partial_overlap() -> None:
    a = BoundingBox(0, 0, 10, 10)  # area 100
    b = BoundingBox(5, 0, 15, 10)  # area 100, overlap [5,10]x[0,10] = 50
    # union = 100 + 100 - 50 = 150 -> iou = 50/150
    assert iou(a, b) == 1 / 3


def test_iou_degenerate_zero_area_box_is_zero() -> None:
    a = BoundingBox(0, 0, 0, 0)
    b = BoundingBox(0, 0, 10, 10)
    assert iou(a, b) == 0.0


# --- match_detections --------------------------------------------------


def test_exact_class_and_matching_box_is_true_positive() -> None:
    result = match_detections([_gt("person", (0, 0, 10, 10))], [_det("person", (0, 0, 10, 10))])
    assert result.counts.tp == 1
    assert result.counts.fp == 0
    assert result.counts.fn == 0


def test_wrong_class_never_counted_as_true_positive() -> None:
    result = match_detections([_gt("car", (0, 0, 10, 10))], [_det("truck", (0, 0, 10, 10))])
    assert result.counts.tp == 0
    assert result.counts.fp == 1
    assert result.counts.fn == 1


def test_no_detection_is_a_false_negative() -> None:
    result = match_detections([_gt("person", (0, 0, 10, 10))], [])
    assert result.counts.tp == 0
    assert result.counts.fn == 1
    assert result.counts.fp == 0


def test_false_detection_with_no_ground_truth_is_a_false_positive() -> None:
    result = match_detections([], [_det("person", (0, 0, 10, 10))])
    assert result.counts.tp == 0
    assert result.counts.fp == 1
    assert result.counts.fn == 0


def test_multiple_predictions_match_multiple_ground_truth() -> None:
    ground_truth = [_gt("person", (0, 0, 10, 10)), _gt("person", (100, 100, 110, 110))]
    predictions = [_det("person", (0, 0, 10, 10)), _det("person", (100, 100, 110, 110))]
    result = match_detections(ground_truth, predictions)
    assert result.counts.tp == 2
    assert result.counts.fp == 0
    assert result.counts.fn == 0


def test_duplicate_predictions_covering_the_same_object_are_not_multiple_true_positives() -> None:
    ground_truth = [_gt("person", (0, 0, 10, 10))]
    predictions = [_det("person", (0, 0, 10, 10)), _det("person", (0, 0, 10, 10))]
    result = match_detections(ground_truth, predictions)
    assert result.counts.tp == 1
    assert result.counts.fp == 1  # the extra duplicate is unmatched
    assert result.counts.fn == 0


def test_configurable_iou_threshold_is_respected() -> None:
    ground_truth = [_gt("person", (0, 0, 10, 10))]
    # overlap iou = 1/3 (see test_iou_known_partial_overlap)
    predictions = [_det("person", (5, 0, 15, 10))]

    strict = match_detections(ground_truth, predictions, iou_threshold=0.5)
    lenient = match_detections(ground_truth, predictions, iou_threshold=0.3)

    assert strict.counts.tp == 0
    assert strict.counts.fn == 1
    assert lenient.counts.tp == 1
    assert lenient.iou_threshold == 0.3


def test_frame_mismatch_never_matches_even_with_perfect_overlap() -> None:
    ground_truth = [_gt("person", (0, 0, 10, 10), frame=5)]
    predictions = [_det("person", (0, 0, 10, 10), frame=50)]
    result = match_detections(ground_truth, predictions)
    assert result.counts.tp == 0
    assert result.counts.fp == 1
    assert result.counts.fn == 1


def test_frame_match_not_required_when_ground_truth_has_no_frame_number() -> None:
    gt = GroundTruthDetection(
        class_name="person", bbox=BoundingBox(0, 0, 10, 10), frame_number=None
    )
    predictions = [_det("person", (0, 0, 10, 10), frame=999)]
    result = match_detections([gt], predictions)
    assert result.counts.tp == 1


# --- Face detection reuses the same matcher, with no identity field -----


def test_face_detection_uses_the_same_matcher() -> None:
    result = match_detections([_gt("face", (0, 0, 10, 10))], [_det("face", (0, 0, 10, 10))])
    assert result.counts.tp == 1


def test_ground_truth_detection_has_no_identity_field() -> None:
    field_names = {f.name for f in dataclasses.fields(GroundTruthDetection)}
    for forbidden in ("identity", "name", "person_id", "embedding"):
        assert forbidden not in field_names
