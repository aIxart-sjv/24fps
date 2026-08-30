"""Tests for app/ai/face_detection.py (Phase 13).

FACE DETECTION ONLY -- these tests protect that no identity/recognition
field ever appears anywhere in this module's output (Master Specification
Section 33: face recognition is not part of the required core). Real-model
tests are skipped, not failed, when the weights are not already cached
(see `tests/fixtures/ai_models.py`).
"""

from __future__ import annotations

import dataclasses

import numpy as np

from app.ai.face_detection import FACE_CLASS_NAME, detect_faces
from app.ai.types import BoundingBox, Detection
from tests.fixtures.ai_models import requires_face_detection_model


def test_face_detection_result_has_no_identity_field() -> None:
    """The `Detection` dataclass a face result uses has no field that
    could carry an identity, an embedding, or a match score against any
    reference set."""
    field_names = {f.name for f in dataclasses.fields(Detection)}

    assert field_names == {
        "class_name",
        "confidence",
        "bbox",
        "frame_number",
        "timestamp_seconds",
        "track_id",
    }
    for forbidden in ("identity", "name", "person_id", "embedding", "match"):
        assert forbidden not in field_names


def test_face_class_name_is_a_plain_label_not_an_identity() -> None:
    assert FACE_CLASS_NAME == "face"


def test_face_detection_dataclass_shape() -> None:
    detection = Detection(
        class_name=FACE_CLASS_NAME,
        confidence=0.91,
        bbox=BoundingBox(x_min=5.0, y_min=5.0, x_max=45.0, y_max=45.0),
        frame_number=3,
        timestamp_seconds=0.12,
    )

    assert detection.class_name == "face"
    assert 0.0 <= detection.confidence <= 1.0
    assert detection.bbox.x_max > detection.bbox.x_min


@requires_face_detection_model
def test_detect_faces_on_blank_frame_finds_nothing() -> None:
    from app.ai.model_registry import load_face_detection_model
    from app.config import get_settings

    model = load_face_detection_model(get_settings().ai_model_root)
    assert model.available

    blank_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    detections = detect_faces(model.model, blank_frame, frame_number=0, timestamp_seconds=0.0)

    assert detections == []


@requires_face_detection_model
def test_detect_faces_never_returns_a_non_face_class_name() -> None:
    from app.ai.model_registry import load_face_detection_model
    from app.config import get_settings

    model = load_face_detection_model(get_settings().ai_model_root)
    assert model.available

    noise = (np.random.default_rng(0).random((240, 320, 3)) * 255).astype(np.uint8)
    detections = detect_faces(model.model, noise, frame_number=0, timestamp_seconds=0.0)

    assert all(d.class_name == FACE_CLASS_NAME for d in detections)
