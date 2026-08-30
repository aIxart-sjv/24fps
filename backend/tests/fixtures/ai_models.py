"""
Shared helper for tests that need the real AI model weights (Phase 13).

Mirrors `tests/fixtures/cp_plus_evidence.py`'s "skip, not fail" pattern:
these tests never trigger a network download during collection -- they
skip cleanly when the weights are not already cached under
`settings.ai_model_root` (e.g. in CI, where no network fetch is
expected), and only exercise real inference when the files are present.
"""

from __future__ import annotations

import pytest

from app.ai.model_registry import DEFAULT_OBJECT_DETECTION_MODEL, FACE_DETECTION_MODEL_FILENAME
from app.config import get_settings


def object_detection_model_available() -> bool:
    """Whether the YOLO object-detection weights are already cached locally."""
    return (get_settings().ai_model_root / DEFAULT_OBJECT_DETECTION_MODEL).is_file()


def face_detection_model_available() -> bool:
    """Whether the YuNet face-detection weights are already cached locally."""
    return (get_settings().ai_model_root / FACE_DETECTION_MODEL_FILENAME).is_file()


requires_object_detection_model = pytest.mark.skipif(
    not object_detection_model_available(),
    reason=(
        "YOLO object-detection weights are not cached under settings.ai_model_root; "
        "this test is skipped, not failed, rather than triggering a network download"
    ),
)

requires_face_detection_model = pytest.mark.skipif(
    not face_detection_model_available(),
    reason=(
        "YuNet face-detection weights are not cached under settings.ai_model_root; "
        "this test is skipped, not failed, rather than triggering a network download"
    ),
)
