"""
Model loading/caching for the AI analysis layer (task Phase 13 scope:
"Load inference models once per worker/job where appropriate... Avoid...
loading the model once per frame, repeated model initialization.").

Every model is loaded exactly once per `AIManager.run_job` call (never per
frame) and every load failure -- missing weights, no network, an
incompatible/corrupt file -- is reported as a clean `ModelLoadResult`
rather than an uncontrolled exception, so a job can report a useful
`PARTIAL`/`FAILED` reason instead of crashing (task: "Handle... model
unavailable... incompatible model").

Model choices and why (task Phase 13 scope: "Inspect the current Python
environment and project documentation before selecting the exact YOLO
package/model... Do not arbitrarily add a huge model or framework"):

- Object detection: `yolov8n.pt`, Ultralytics' smallest ("nano") COCO-
  pretrained YOLOv8 checkpoint (~6.2 MB) -- `docs/SIH_TECH_STACK.md`
  Section 8 names YOLO/Ultralytics as the chosen technology; "nano" is the
  practical choice for a development laptop, not "a huge model."
  Ultralytics resolves this bare filename to its own official GitHub
  release asset and downloads it into the given path on first use.
- Face detection: OpenCV's built-in `FaceDetectorYN` (the "YuNet" model),
  an official, small (232 KB) ONNX model published by the OpenCV Zoo
  project. Verified in this environment that `opencv-python` 5.x no
  longer bundles Haar cascade XML data (`cv2.data.haarcascades` is empty)
  -- YuNet stays inside the already-chosen OpenCV stack (no new pip
  package), is not "a huge model," and (unlike Haar cascades) reports a
  real per-detection confidence score.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_OBJECT_DETECTION_MODEL",
    "FACE_DETECTION_MODEL_FILENAME",
    "FACE_DETECTION_MODEL_SHA256",
    "FACE_DETECTION_MODEL_URL",
    "FACE_DETECTION_MODEL_VERSION",
    "OBJECT_DETECTION_MODEL_VERSION",
    "ModelLoadResult",
    "load_face_detection_model",
    "load_object_detection_model",
]

DEFAULT_OBJECT_DETECTION_MODEL = "yolov8n.pt"
OBJECT_DETECTION_MODEL_VERSION = "yolov8n"

FACE_DETECTION_MODEL_FILENAME = "face_detection_yunet_2023mar.onnx"
FACE_DETECTION_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
#: Verified by downloading and hashing the file directly during Phase 13
#: development -- checked on every download so a corrupted/tampered fetch
#: is never silently used for forensic analysis.
FACE_DETECTION_MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
FACE_DETECTION_MODEL_VERSION = "yunet_2023mar"

_FACE_DETECTION_INPUT_SIZE = (320, 320)


@dataclass(frozen=True)
class ModelLoadResult:
    """Outcome of one model load attempt.

    `model` is intentionally untyped (`object`) -- callers that need the
    concrete model object know which loader they called and narrow it
    themselves; this dataclass's job is only to report success/failure
    uniformly.
    """

    available: bool
    model: object | None
    model_name: str
    model_version: str
    error: str | None = None


def load_object_detection_model(model_root: Path, *, device: str = "cpu") -> ModelLoadResult:
    """Load (downloading into `model_root` on first use) the YOLO object-detection model.

    Args:
        model_root: Directory to cache/resolve model weights in
            (`settings.ai_model_root`).
        device: Inference device to move the loaded model onto.

    Returns:
        A `ModelLoadResult`. Never raises for a missing/incompatible
        model or a network failure during download.
    """
    try:
        # ultralytics does not mark `YOLO` in its top-level `__all__`, so
        # mypy --strict's implicit-reexport check flags this import even
        # though it is the package's own documented public API
        # (https://docs.ultralytics.com/).
        from ultralytics import YOLO  # type: ignore[attr-defined]
    except ImportError as exc:
        return ModelLoadResult(
            available=False,
            model=None,
            model_name=DEFAULT_OBJECT_DETECTION_MODEL,
            model_version=OBJECT_DETECTION_MODEL_VERSION,
            error=f"ultralytics is not installed: {exc}",
        )

    model_root.mkdir(parents=True, exist_ok=True)
    weights_path = model_root / DEFAULT_OBJECT_DETECTION_MODEL
    try:
        model = YOLO(str(weights_path))
        model.to(device)
    except Exception as exc:
        return ModelLoadResult(
            available=False,
            model=None,
            model_name=DEFAULT_OBJECT_DETECTION_MODEL,
            model_version=OBJECT_DETECTION_MODEL_VERSION,
            error=f"failed to load object detection model {weights_path}: {exc}",
        )

    return ModelLoadResult(
        available=True,
        model=model,
        model_name=DEFAULT_OBJECT_DETECTION_MODEL,
        model_version=OBJECT_DETECTION_MODEL_VERSION,
    )


def _ensure_face_model_weights(model_root: Path) -> Path:
    """Return the local YuNet weights path, downloading and integrity-checking it if absent."""
    weights_path = model_root / FACE_DETECTION_MODEL_FILENAME
    if weights_path.exists():
        return weights_path

    model_root.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(FACE_DETECTION_MODEL_URL, timeout=30) as response:  # noqa: S310
        data = response.read()

    digest = hashlib.sha256(data).hexdigest()
    if digest != FACE_DETECTION_MODEL_SHA256:
        raise ValueError(
            f"downloaded face detection model hash mismatch: expected "
            f"{FACE_DETECTION_MODEL_SHA256}, got {digest}"
        )

    weights_path.write_bytes(data)
    return weights_path


def load_face_detection_model(model_root: Path) -> ModelLoadResult:
    """Load (downloading into `model_root` on first use) the YuNet face-detection model.

    Args:
        model_root: Directory to cache/resolve model weights in
            (`settings.ai_model_root`).

    Returns:
        A `ModelLoadResult`. Never raises for a network failure, a hash
        mismatch, or an OpenCV load failure.
    """
    try:
        import cv2
    except ImportError as exc:
        return ModelLoadResult(
            available=False,
            model=None,
            model_name=FACE_DETECTION_MODEL_FILENAME,
            model_version=FACE_DETECTION_MODEL_VERSION,
            error=f"opencv-python is not installed: {exc}",
        )

    try:
        weights_path = _ensure_face_model_weights(model_root)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return ModelLoadResult(
            available=False,
            model=None,
            model_name=FACE_DETECTION_MODEL_FILENAME,
            model_version=FACE_DETECTION_MODEL_VERSION,
            error=f"face detection model unavailable: {exc}",
        )

    try:
        # cv2's bundled stubs lag behind its actual runtime surface;
        # `FaceDetectorYN_create` exists and works at runtime (verified in
        # this session) even though it is not declared in the stub.
        detector: Any = cv2.FaceDetectorYN_create(  # type: ignore[attr-defined]
            str(weights_path), "", _FACE_DETECTION_INPUT_SIZE
        )
    except Exception as exc:
        return ModelLoadResult(
            available=False,
            model=None,
            model_name=FACE_DETECTION_MODEL_FILENAME,
            model_version=FACE_DETECTION_MODEL_VERSION,
            error=f"failed to load face detection model {weights_path}: {exc}",
        )

    return ModelLoadResult(
        available=True,
        model=detector,
        model_name=FACE_DETECTION_MODEL_FILENAME,
        model_version=FACE_DETECTION_MODEL_VERSION,
    )
