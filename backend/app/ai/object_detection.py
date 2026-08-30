"""
Object detection over selected video frames (task Phase 13 scope, Master
Specification Section 31 "Object Detection").

A thin wrapper around an already-loaded Ultralytics YOLO model
(`app.ai.model_registry.load_object_detection_model`) -- this module never
loads a model itself and never decodes video; it only runs inference on
frames the caller already has in memory and returns plain
`app.ai.types.Detection` objects. Object detection answers "what objects
are present and where" -- never "who."
"""

from __future__ import annotations

from typing import Any

from app.ai.types import BoundingBox, Detection

__all__ = ["detect_objects"]


def detect_objects(
    model: Any,
    frame: Any,
    *,
    frame_number: int,
    timestamp_seconds: float,
    confidence_threshold: float = 0.25,
    device: str = "cpu",
    classes: list[str] | None = None,
) -> list[Detection]:
    """Run one loaded YOLO model over one already-decoded frame.

    Args:
        model: A loaded `ultralytics.YOLO` instance (from
            `app.ai.model_registry.load_object_detection_model`).
        frame: One decoded BGR frame (`numpy.ndarray`, as returned by
            `cv2.VideoCapture.read`).
        frame_number: The source video's frame index this frame came from.
        timestamp_seconds: The frame's timestamp relative to the start of
            the source video.
        confidence_threshold: Minimum detection confidence to keep. Always
            recorded by the caller as a job parameter for reproducibility
            (task: "Record configured thresholds as job parameters").
        device: Inference device string (`"cpu"` or `"cuda:0"`).
        classes: Optional allow-list of class names to keep. `None` means
            no filtering -- every class the model supports is reported.

    Returns:
        Every detection above `confidence_threshold`, class-filtered if
        `classes` was given. Never invents a confidence value: each score
        is exactly what the model reported.
    """
    results = model.predict(source=frame, device=device, conf=confidence_threshold, verbose=False)
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return []

    names = model.names
    allowed = set(classes) if classes is not None else None

    detections: list[Detection] = []
    xyxy = boxes.xyxy.tolist()
    confidences = boxes.conf.tolist()
    class_indices = boxes.cls.tolist()
    for (x_min, y_min, x_max, y_max), confidence, class_index in zip(
        xyxy, confidences, class_indices, strict=True
    ):
        class_name = names[int(class_index)]
        if allowed is not None and class_name not in allowed:
            continue
        detections.append(
            Detection(
                class_name=class_name,
                confidence=float(confidence),
                bbox=BoundingBox(
                    x_min=float(x_min), y_min=float(y_min), x_max=float(x_max), y_max=float(y_max)
                ),
                frame_number=frame_number,
                timestamp_seconds=timestamp_seconds,
            )
        )
    return detections
