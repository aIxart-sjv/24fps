"""
Motion detection over selected video frames (task Phase 13 scope, Master
Specification Section 34 "Motion Detection").

Classical computer vision, per `docs/SIH_TECH_STACK.md` Section 11
("Classical computer vision first... Motion detection does not
automatically require AI. Use the simplest method that works."): grayscale
frame differencing between consecutive sampled frames, thresholded, with
changed regions extracted via contour detection. Deterministic given fixed
`threshold`/`min_area` parameters, so it is directly repeatable in tests
(task: "The motion algorithm should be deterministic enough for
repeatable tests.").

Motion detection answers "did something change here" -- never "what" or
"who." Operates over the *same* sampled-frame sequence used for object/
face detection in the same job (one sampling regime per job, not a
second, motion-specific one).
"""

from __future__ import annotations

from typing import Any

from app.ai.types import BoundingBox, MotionEventResult, MotionRegion

__all__ = ["DEFAULT_MIN_AREA", "DEFAULT_THRESHOLD", "METHOD_NAME", "detect_motion_events"]

METHOD_NAME = "frame_differencing"

#: Pixel-intensity difference (0-255, after an 8-bit grayscale absolute
#: difference) above which a pixel counts as "changed". 25 is a
#: conventional starting point for this technique (small enough to catch
#: real motion, large enough to reject ordinary compression noise) --
#: always recorded as a job parameter, never silently varied.
DEFAULT_THRESHOLD = 25

#: Minimum contour area (in pixels) for a changed region to be reported --
#: filters single-pixel/compression-noise speckling without requiring a
#: trained model.
DEFAULT_MIN_AREA = 500.0


def detect_motion_events(
    samples: list[tuple[int, float, Any]],
    *,
    threshold: int = DEFAULT_THRESHOLD,
    min_area: float = DEFAULT_MIN_AREA,
) -> list[MotionEventResult]:
    """Detect contiguous motion spans across a sequence of sampled frames.

    Args:
        samples: `(frame_number, timestamp_seconds, frame)` tuples, in
            ascending time order, from the same sampled-frame sequence
            used for the job's other analysis types. `frame` is a decoded
            BGR `numpy.ndarray`.
        threshold: See `DEFAULT_THRESHOLD`.
        min_area: See `DEFAULT_MIN_AREA`.

    Returns:
        One `MotionEventResult` per contiguous run of consecutive sample
        pairs where a changed region was found. `score` is the largest
        per-pair total changed-pixel area seen during that event -- an
        arbitrary but deterministic, documented magnitude, never a
        calibrated probability. Fewer than 2 samples yields no events
        (nothing to difference).
    """
    if len(samples) < 2:
        return []

    import cv2

    events: list[MotionEventResult] = []
    active_start: float | None = None
    active_end: float | None = None
    active_regions: list[MotionRegion] = []
    active_scores: list[float] = []

    prev_gray = None
    prev_timestamp: float | None = None

    for frame_number, timestamp_seconds, frame in samples:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if prev_gray is None:
            prev_gray = gray
            prev_timestamp = timestamp_seconds
            continue

        diff = cv2.absdiff(prev_gray, gray)
        _, thresholded = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
        thresholded = cv2.dilate(thresholded, None, iterations=2)
        contours, _ = cv2.findContours(thresholded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions: list[MotionRegion] = []
        pair_score = 0.0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            regions.append(
                MotionRegion(
                    frame_number=frame_number,
                    timestamp_seconds=timestamp_seconds,
                    bbox=BoundingBox(
                        x_min=float(x), y_min=float(y), x_max=float(x + w), y_max=float(y + h)
                    ),
                )
            )
            pair_score += float(area)

        if regions:
            if active_start is None:
                active_start = prev_timestamp
            active_end = timestamp_seconds
            active_regions.extend(regions)
            active_scores.append(pair_score)
        elif active_start is not None and active_end is not None:
            events.append(
                MotionEventResult(
                    start_time_seconds=active_start,
                    end_time_seconds=active_end,
                    regions=active_regions,
                    score=max(active_scores),
                )
            )
            active_start, active_end, active_regions, active_scores = None, None, [], []

        prev_gray = gray
        prev_timestamp = timestamp_seconds

    if active_start is not None and active_end is not None:
        events.append(
            MotionEventResult(
                start_time_seconds=active_start,
                end_time_seconds=active_end,
                regions=active_regions,
                score=max(active_scores) if active_scores else 0.0,
            )
        )

    return events
