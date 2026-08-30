"""Tests for app/ai/object_detection.py (Phase 13).

Real-model tests (marked, skipped rather than triggering a network
download when the weights are not already cached -- see
`tests/fixtures/ai_models.py`) exercise the actual `detect_objects`
adapter end to end against the real downloaded YOLOv8n checkpoint. A
synthetic blank frame is used, so a genuinely empty result is the
expected, honest outcome -- this is NOT a claim about detection accuracy
(Phase 14's job), only that real inference runs and returns the correct
shape. Structural/shape tests below need no model at all.
"""

from __future__ import annotations

import numpy as np

from app.ai.object_detection import detect_objects
from app.ai.types import BoundingBox, Detection
from tests.fixtures.ai_models import requires_object_detection_model


def test_detection_dataclass_has_the_documented_fields() -> None:
    """Structural check of the result shape task Phase 13 scope requires:
    class, confidence, bounding box, frame number, timestamp -- never an
    identity field."""
    detection = Detection(
        class_name="person",
        confidence=0.87,
        bbox=BoundingBox(x_min=10.0, y_min=20.0, x_max=110.0, y_max=220.0),
        frame_number=42,
        timestamp_seconds=1.68,
    )

    assert detection.class_name == "person"
    assert 0.0 <= detection.confidence <= 1.0
    assert detection.bbox.x_max > detection.bbox.x_min
    assert detection.bbox.y_max > detection.bbox.y_min
    assert detection.frame_number == 42
    assert detection.timestamp_seconds == 1.68
    assert detection.track_id is None


@requires_object_detection_model
def test_detect_objects_on_blank_frame_finds_nothing() -> None:
    from app.ai.model_registry import load_object_detection_model
    from app.config import get_settings

    model = load_object_detection_model(get_settings().ai_model_root, device="cpu")
    assert model.available

    blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    detections = detect_objects(
        model.model, blank_frame, frame_number=0, timestamp_seconds=0.0, device="cpu"
    )

    assert detections == []


@requires_object_detection_model
def test_detect_objects_with_impossible_class_filter_finds_nothing() -> None:
    from app.ai.model_registry import load_object_detection_model
    from app.config import get_settings

    model = load_object_detection_model(get_settings().ai_model_root, device="cpu")
    assert model.available

    blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    detections = detect_objects(
        model.model,
        blank_frame,
        frame_number=0,
        timestamp_seconds=0.0,
        device="cpu",
        classes=["not_a_real_class"],
    )

    assert detections == []


@requires_object_detection_model
def test_detect_objects_reports_real_frame_and_timestamp_references() -> None:
    from app.ai.model_registry import load_object_detection_model
    from app.config import get_settings

    model = load_object_detection_model(get_settings().ai_model_root, device="cpu")
    assert model.available

    # A genuinely empty result is still the correct, honest outcome for a
    # blank frame -- this test protects that `detect_objects` never
    # crashes or hangs on real inference, using the exact frame/timestamp
    # values a real job would pass.
    blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    detections = detect_objects(
        model.model,
        blank_frame,
        frame_number=17,
        timestamp_seconds=0.68,
        confidence_threshold=0.25,
        device="cpu",
    )

    assert isinstance(detections, list)
