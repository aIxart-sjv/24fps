"""
Business logic for deterministic visual-attribute video search (Phase 23).
See `app.ai.attribute_search`'s module docstring for why this is a
deterministic HSV color classifier and not a vision-language model.

This is the DB-aware orchestration layer: it never re-runs object
detection (that already happened, via `app.core.ai_manager.AIManager`,
whenever an examiner chose to run it) -- it only reads already-persisted
`AIResult` rows and re-opens the exact `source_artifact` those results
were already computed from (mirroring `AIManager._process_recording`'s
own re-seek-by-frame-number pattern) to classify each candidate
detection's upper-body color. No detection model is invoked here, so
this search never fails merely because a YOLO weight file is
unavailable -- it fails only if no AI detections exist yet to search
over, which it reports honestly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.ai.attribute_search import (
    ATTRIBUTE_SEARCH_METHOD,
    ATTRIBUTE_SEARCH_VERSION,
    SUPPORTED_CLASSES,
    SUPPORTED_COLORS,
    QueryAttributes,
    classify_dominant_color,
    parse_query,
)
from app.models import AIResult, Artifact, Recording

__all__ = ["VideoSearchManager", "VideoSearchResult", "VideoSearchSighting"]

#: Two detections merge into the same reported "sighting" when they are
#: on the same recording and no more than this many seconds apart --
#: matching `app.timeline.correlation.DEFAULT_MAX_GAP_SECONDS`'s order of
#: magnitude for "temporally continuous", not independently invented.
_SIGHTING_MERGE_GAP_SECONDS = 5.0

#: A crop this small cannot yield a meaningful color reading -- skip
#: rather than report a low-confidence bucket from a handful of pixels.
_MIN_CROP_DIMENSION_PX = 6


@dataclass(frozen=True)
class VideoSearchSighting:
    """One grouped visual-attribute match, spanning one or more
    consecutive detections on the same recording."""

    recording_id: int
    camera_id: str | None
    start_frame: int
    end_frame: int
    start_timestamp: str | None
    end_timestamp: str | None
    matched_color: str
    match_confidence: float
    ai_result_ids: list[int]
    track_id: int | None
    #: `AIResult.class_name` for this sighting's detections -- every
    #: detection in one sighting shares the same class (the search itself
    #: is always scoped to one `object_class`), included per-row so a
    #: results table never has to join back to the parent query to show
    #: it (task Phase 24 scope, "Search Result Details").
    class_name: str
    #: `AIResult.source_artifact` the underlying detections were computed
    #: from -- traceability back to the exact derived media artifact.
    source_artifact: int


@dataclass(frozen=True)
class VideoSearchResult:
    """The full, traceable outcome of one search request."""

    case_id: int
    query: str
    attributes: QueryAttributes
    method: str
    method_version: str
    supported_colors: list[str]
    supported_classes: list[str]
    recognized: bool
    sightings: list[VideoSearchSighting] = field(default_factory=list)
    detections_examined: int = 0
    warnings: list[str] = field(default_factory=list)


class VideoSearchManager:
    """Service layer for running deterministic attribute-based video search."""

    @staticmethod
    def search(
        db: Session, *, case_id: int, query: str, recording_ids: list[int] | None = None
    ) -> VideoSearchResult:
        """Run one attribute search over a case's already-computed AI detections.

        Args:
            db: Database session.
            case_id: The case to search within.
            query: Free-text query (e.g. `"red shirt guy"`).
            recording_ids: Optional recording scope. `None` searches every
                recording in the case that already has AI results.

        Returns:
            A `VideoSearchResult`. Never raises for "nothing found" or
            "query names no recognized attribute" -- both are reported
            structurally via `recognized`/`sightings`/`warnings`.
        """
        attributes = parse_query(query)
        base = VideoSearchResult(
            case_id=case_id,
            query=query,
            attributes=attributes,
            method=ATTRIBUTE_SEARCH_METHOD,
            method_version=ATTRIBUTE_SEARCH_VERSION,
            supported_colors=list(SUPPORTED_COLORS),
            supported_classes=sorted(set(SUPPORTED_CLASSES.values())),
            recognized=attributes.color is not None,
        )
        if attributes.color is None:
            base.warnings.append(
                "no recognized color attribute in query; this deterministic search matches a "
                f"closed vocabulary of colors ({', '.join(SUPPORTED_COLORS)}) and object classes "
                f"({', '.join(sorted(set(SUPPORTED_CLASSES.values())))}) -- it cannot interpret "
                "open-ended natural language."
            )
            return base

        object_class = attributes.object_class or "person"

        query_ai_results = db.query(AIResult).filter(
            AIResult.case_id == case_id, AIResult.class_name == object_class
        )
        if recording_ids:
            query_ai_results = query_ai_results.filter(AIResult.recording_id.in_(recording_ids))
        detections = query_ai_results.order_by(AIResult.recording_id, AIResult.frame_number).all()

        if not detections:
            base.warnings.append(
                f"no existing {object_class!r} detections found for this case -- run AI analysis "
                "(object detection) on the relevant recordings first; this search only classifies "
                "already-detected objects, it does not run detection itself."
            )
            return base

        by_artifact: dict[int, list[AIResult]] = {}
        for detection in detections:
            by_artifact.setdefault(detection.source_artifact, []).append(detection)

        matches: list[tuple[AIResult, float]] = []
        for artifact_id, group in by_artifact.items():
            matches.extend(
                VideoSearchManager._classify_group(db, artifact_id, group, attributes.color)
            )

        base_result = VideoSearchResult(
            case_id=base.case_id,
            query=base.query,
            attributes=base.attributes,
            method=base.method,
            method_version=base.method_version,
            supported_colors=base.supported_colors,
            supported_classes=base.supported_classes,
            recognized=True,
            detections_examined=len(detections),
            sightings=VideoSearchManager._group_into_sightings(matches, attributes.color),
        )
        if not base_result.sightings:
            base_result.warnings.append(
                f"{len(detections)} {object_class!r} detection(s) were examined; none matched "
                f"color {attributes.color!r}. This is a negative result for this deterministic "
                "classifier, not proof the attribute is absent from the footage."
            )
        return base_result

    @staticmethod
    def _classify_group(
        db: Session, artifact_id: int, group: list[AIResult], query_color: str
    ) -> list[tuple[AIResult, float]]:
        artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if artifact is None or not Path(artifact.path).is_file():
            return []

        matches: list[tuple[AIResult, float]] = []
        capture = cv2.VideoCapture(artifact.path)
        try:
            if not capture.isOpened():
                return []
            for detection in group:
                capture.set(cv2.CAP_PROP_POS_FRAMES, detection.frame_number)
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                crop = VideoSearchManager._upper_body_crop(frame, detection)
                if crop is None:
                    continue
                color, confidence = classify_dominant_color(crop)
                if color == query_color:
                    matches.append((detection, confidence))
        finally:
            capture.release()
        return matches

    @staticmethod
    def _upper_body_crop(frame: np.ndarray, detection: AIResult) -> np.ndarray | None:
        height, width = frame.shape[:2]
        x_min = max(0, min(int(detection.bbox_x_min), width - 1))
        x_max = max(0, min(int(detection.bbox_x_max), width))
        y_min = max(0, min(int(detection.bbox_y_min), height - 1))
        y_max = max(0, min(int(detection.bbox_y_max), height))
        if x_max <= x_min or y_max <= y_min:
            return None

        box_height = y_max - y_min
        box_width = x_max - x_min
        # Upper-body/torso band: skip the head (top ~25%) and legs (below
        # ~65%), and inset the sides slightly to reduce background bleed.
        torso_top = y_min + int(box_height * 0.25)
        torso_bottom = y_min + int(box_height * 0.65)
        inset = int(box_width * 0.1)
        crop = frame[torso_top:torso_bottom, x_min + inset : x_max - inset]
        if crop.shape[0] < _MIN_CROP_DIMENSION_PX or crop.shape[1] < _MIN_CROP_DIMENSION_PX:
            return None
        return crop

    @staticmethod
    def _group_into_sightings(
        matches: list[tuple[AIResult, float]], matched_color: str
    ) -> list[VideoSearchSighting]:
        if not matches:
            return []

        by_recording: dict[int, list[tuple[AIResult, float]]] = {}
        for detection, confidence in matches:
            by_recording.setdefault(detection.recording_id, []).append((detection, confidence))

        sightings: list[VideoSearchSighting] = []
        for recording_id, group in by_recording.items():
            group.sort(key=lambda pair: pair[0].frame_number)
            current: list[tuple[AIResult, float]] = [group[0]]

            def _flush(bucket: list[tuple[AIResult, float]]) -> None:
                detections = [d for d, _ in bucket]
                confidences = [c for _, c in bucket]
                first, last = detections[0], detections[-1]
                sightings.append(
                    VideoSearchSighting(
                        recording_id=recording_id,
                        camera_id=_camera_id_for(first.recording),
                        start_frame=first.frame_number,
                        end_frame=last.frame_number,
                        start_timestamp=first.timestamp.isoformat() if first.timestamp else None,
                        end_timestamp=last.timestamp.isoformat() if last.timestamp else None,
                        matched_color=matched_color,
                        match_confidence=sum(confidences) / len(confidences),
                        ai_result_ids=[d.id for d in detections],
                        track_id=first.track_id,
                        class_name=first.class_name,
                        source_artifact=first.source_artifact,
                    )
                )

            for detection, confidence in group[1:]:
                prev_detection = current[-1][0]
                gap = _seconds_gap(prev_detection, detection)
                same_track = (
                    prev_detection.track_id is not None
                    and prev_detection.track_id == detection.track_id
                )
                if same_track or (gap is not None and gap <= _SIGHTING_MERGE_GAP_SECONDS):
                    current.append((detection, confidence))
                else:
                    _flush(current)
                    current = [(detection, confidence)]
            _flush(current)

        sightings.sort(key=lambda s: (s.recording_id, s.start_frame))
        return sightings


def _camera_id_for(recording: Recording) -> str | None:
    if recording.camera_id is not None:
        return recording.camera_id
    if recording.channel is not None:
        return str(recording.channel)
    return None


def _seconds_gap(a: AIResult, b: AIResult) -> float | None:
    if a.timestamp is None or b.timestamp is None:
        return None
    return abs((b.timestamp - a.timestamp).total_seconds())
