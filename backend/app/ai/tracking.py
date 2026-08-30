"""
Object tracking across selected video frames (task Phase 13 scope, Master
Specification Section 32 "Object Tracking").

Wraps Ultralytics' built-in tracking mode (`model.track(...)`), which
ships both candidate trackers `docs/SIH_TECH_STACK.md` Section 9 names
(ByteTrack, BoT-SORT) -- no separate tracker package or from-scratch
implementation is needed. Tracking is run over the *same* sampled-frame
sequence used for object detection in the same job, not the full video.

Tracking never proves identity (Master Specification Section 32: "Tracking
does not automatically prove identity."). Nothing here computes an
embedding, compares faces, or maintains any identity registry -- a track
is a run of frame-to-frame associated detections, identified only by a
job-scoped integer.
"""

from __future__ import annotations

from typing import Any

from app.ai.types import BoundingBox, Track, TrackPoint

__all__ = ["BOTSORT_TRACKER", "BYTETRACK_TRACKER", "run_tracking"]

#: Ultralytics' bundled tracker config names -- both candidates
#: `docs/SIH_TECH_STACK.md` Section 9 names ("Start with whichever
#: performs better on our CCTV footage. Do not permanently lock the
#: tracker before testing."); the caller selects one per job.
BYTETRACK_TRACKER = "bytetrack.yaml"
BOTSORT_TRACKER = "botsort.yaml"


def run_tracking(
    model: Any,
    frames: list[tuple[int, float, Any]],
    *,
    tracker: str = BYTETRACK_TRACKER,
    confidence_threshold: float = 0.25,
    device: str = "cpu",
    classes: list[str] | None = None,
) -> list[Track]:
    """Run tracking over a sequence of already-decoded, time-ordered frames.

    Args:
        model: A loaded `ultralytics.YOLO` instance (the same object used
            for object detection -- tracking reuses the same detector).
        frames: `(frame_number, timestamp_seconds, frame)` tuples, in
            ascending time order.
        tracker: `BYTETRACK_TRACKER` or `BOTSORT_TRACKER`.
        confidence_threshold: Minimum per-detection confidence to feed the
            tracker.
        device: Inference device string (`"cpu"` or `"cuda:0"`).
        classes: Optional allow-list of class names to track. `None`
            means no filtering.

    Returns:
        One `Track` per distinct track ID the tracker produced, ordered by
        `track_id`. An empty list if no frames were supplied or nothing
        was tracked.
    """
    if not frames:
        return []

    frame_numbers = [frame_number for frame_number, _, _ in frames]
    timestamps = [timestamp for _, timestamp, _ in frames]
    raw_frames = [frame for _, _, frame in frames]

    results = model.track(
        source=raw_frames,
        tracker=tracker,
        persist=True,
        device=device,
        conf=confidence_threshold,
        verbose=False,
    )

    names = model.names
    allowed = set(classes) if classes is not None else None

    points_by_track: dict[int, list[TrackPoint]] = {}
    class_by_track: dict[int, str] = {}

    for index, result in enumerate(results):
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            continue
        frame_number = frame_numbers[index]
        timestamp_seconds = timestamps[index]
        for (x_min, y_min, x_max, y_max), confidence, class_index, track_id in zip(
            boxes.xyxy.tolist(),
            boxes.conf.tolist(),
            boxes.cls.tolist(),
            boxes.id.tolist(),
            strict=True,
        ):
            class_name = names[int(class_index)]
            if allowed is not None and class_name not in allowed:
                continue
            tid = int(track_id)
            points_by_track.setdefault(tid, []).append(
                TrackPoint(
                    frame_number=frame_number,
                    timestamp_seconds=timestamp_seconds,
                    bbox=BoundingBox(
                        x_min=float(x_min),
                        y_min=float(y_min),
                        x_max=float(x_max),
                        y_max=float(y_max),
                    ),
                    confidence=float(confidence),
                )
            )
            class_by_track.setdefault(tid, class_name)

    tracks: list[Track] = []
    for track_id, points in points_by_track.items():
        ordered = sorted(points, key=lambda point: point.frame_number)
        confidences = [point.confidence for point in ordered]
        tracks.append(
            Track(
                track_id=track_id,
                class_name=class_by_track[track_id],
                first_seen_frame=ordered[0].frame_number,
                first_seen_timestamp_seconds=ordered[0].timestamp_seconds,
                last_seen_frame=ordered[-1].frame_number,
                last_seen_timestamp_seconds=ordered[-1].timestamp_seconds,
                trajectory=ordered,
                frame_count=len(ordered),
                average_confidence=sum(confidences) / len(confidences),
            )
        )

    return sorted(tracks, key=lambda track: track.track_id)
