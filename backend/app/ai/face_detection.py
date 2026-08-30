"""
Face detection over selected video frames (task Phase 13 scope, Master
Specification Section 33 "Face Detection").

Face detection ONLY -- this module answers "is there a face here", never
"whose face is it." No embeddings, no identity matching, no comparison
against any reference set exist anywhere in this module or are computed
from its output (Master Specification Section 33: "Face recognition is
not part of the required core.").

A thin wrapper around an already-loaded `cv2.FaceDetectorYN` instance
(`app.ai.model_registry.load_face_detection_model`) -- never loads a model
itself and never decodes video.
"""

from __future__ import annotations

from typing import Any

from app.ai.types import BoundingBox, Detection

__all__ = ["FACE_CLASS_NAME", "detect_faces"]

#: The single, non-identity label every result from this module carries.
FACE_CLASS_NAME = "face"


def detect_faces(
    detector: Any,
    frame: Any,
    *,
    frame_number: int,
    timestamp_seconds: float,
    confidence_threshold: float = 0.6,
) -> list[Detection]:
    """Run one loaded YuNet detector over one already-decoded frame.

    Args:
        detector: A loaded `cv2.FaceDetectorYN` instance (from
            `app.ai.model_registry.load_face_detection_model`).
        frame: One decoded BGR frame (`numpy.ndarray`).
        frame_number: The source video's frame index this frame came from.
        timestamp_seconds: The frame's timestamp relative to the start of
            the source video.
        confidence_threshold: Minimum detection score to keep (YuNet's
            own reported score, never fabricated).

    Returns:
        Every face detection above `confidence_threshold`. `class_name`
        is always `FACE_CLASS_NAME` -- never an identity label.
    """
    height, width = frame.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(frame)
    if faces is None:
        return []

    detections: list[Detection] = []
    for face in faces:
        # YuNet's row layout: x, y, w, h, <5 landmark point pairs>, score.
        x, y, w, h, score = face[0], face[1], face[2], face[3], face[-1]
        if float(score) < confidence_threshold:
            continue
        detections.append(
            Detection(
                class_name=FACE_CLASS_NAME,
                confidence=float(score),
                bbox=BoundingBox(
                    x_min=float(x), y_min=float(y), x_max=float(x + w), y_max=float(y + h)
                ),
                frame_number=frame_number,
                timestamp_seconds=timestamp_seconds,
            )
        )
    return detections
