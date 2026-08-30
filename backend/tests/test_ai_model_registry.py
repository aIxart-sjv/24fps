"""Tests for app/ai/model_registry.py (Phase 13): real model loading plus
deterministic missing/incompatible-model handling that needs no network."""

from __future__ import annotations

from pathlib import Path

from app.ai.model_registry import (
    FACE_DETECTION_MODEL_FILENAME,
    load_face_detection_model,
    load_object_detection_model,
)
from tests.fixtures.ai_models import (
    requires_face_detection_model,
    requires_object_detection_model,
)


def test_object_detection_model_load_failure_is_reported_cleanly(tmp_path: Path) -> None:
    """A directory with no usable weights and no network must report
    `available=False`, never raise."""
    unreachable_root = tmp_path / "no_such_models_dir_marker"
    # Corrupt/incompatible weights file: a real download would overwrite
    # this, but a garbage file at the expected path exercises the "load
    # failed" path deterministically, without depending on the network.
    unreachable_root.mkdir()
    (unreachable_root / "yolov8n.pt").write_bytes(b"not a real checkpoint")

    result = load_object_detection_model(unreachable_root, device="cpu")

    assert result.available is False
    assert result.model is None
    assert result.error is not None


def test_face_detection_model_load_failure_is_reported_cleanly(tmp_path: Path) -> None:
    corrupt_root = tmp_path / "corrupt_models"
    corrupt_root.mkdir()
    (corrupt_root / FACE_DETECTION_MODEL_FILENAME).write_bytes(b"not a real onnx file")

    result = load_face_detection_model(corrupt_root)

    assert result.available is False
    assert result.model is None
    assert result.error is not None


@requires_object_detection_model
def test_object_detection_model_loads_successfully_and_reports_version() -> None:
    from app.config import get_settings

    result = load_object_detection_model(get_settings().ai_model_root, device="cpu")

    assert result.available is True
    assert result.model is not None
    assert result.model_name
    assert result.model_version
    assert result.error is None


@requires_face_detection_model
def test_face_detection_model_loads_successfully_and_reports_version() -> None:
    from app.config import get_settings

    result = load_face_detection_model(get_settings().ai_model_root)

    assert result.available is True
    assert result.model is not None
    assert result.model_name == FACE_DETECTION_MODEL_FILENAME
    assert result.model_version
    assert result.error is None
