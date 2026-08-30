"""
Shared, pure types for the AI analysis layer (Phase 13, Master Specification
Section 30 "AI Backend"). No DB, no HTTP, no model-inference code lives
here -- just the vocabulary the rest of `app.ai` and `app.core.ai_manager`
share.

Every name in this module is deliberately conservative about what it
claims: `Detection`/`Track` describe *observations* (a class label, a
confidence score, a bounding box, a track identifier), never an identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AnalysisType(str, Enum):
    """The AI capabilities Master Specification Section 30 requires.

    Matches `Job.analysis_types` (a JSON list of these values) and
    `AIResult.analysis_type` exactly -- one shared vocabulary.
    """

    OBJECT_DETECTION = "object_detection"
    FACE_DETECTION = "face_detection"
    MOTION_DETECTION = "motion_detection"
    OBJECT_TRACKING = "object_tracking"


@dataclass(frozen=True)
class BoundingBox:
    """A detection's location in one frame, in pixel coordinates.

    Matches the exact 4-field shape both the Master Specification and the
    NTRO requirements name explicitly (`x_min, y_min, x_max, y_max` /
    `[x1,y1,x2,y2]`) -- never an opaque string.
    """

    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass(frozen=True)
class Detection:
    """One object/face observation on one sampled frame.

    `class_name` is a plain label ("person", "car", "face") -- never an
    identity. `track_id` is populated only when tracking (Phase 13's
    `app.ai.tracking`) was actually run and associated this detection with
    a track; it is a track reference, not identity confirmation.
    """

    class_name: str
    confidence: float
    bbox: BoundingBox
    frame_number: int
    timestamp_seconds: float
    track_id: int | None = None


@dataclass(frozen=True)
class TrackPoint:
    """One frame's position of a tracked object, as part of its trajectory."""

    frame_number: int
    timestamp_seconds: float
    bbox: BoundingBox
    confidence: float


@dataclass(frozen=True)
class Track:
    """One aggregated object track across multiple sampled frames.

    Master Specification Section 32: "Tracking does not automatically
    prove identity." This dataclass never carries any identity field --
    only a track reference, a class label, and a trajectory of positions.
    """

    track_id: int
    class_name: str
    first_seen_frame: int
    first_seen_timestamp_seconds: float
    last_seen_frame: int
    last_seen_timestamp_seconds: float
    trajectory: list[TrackPoint]
    frame_count: int
    average_confidence: float


@dataclass(frozen=True)
class MotionRegion:
    """One changed-pixel region found in a single sampled-frame comparison."""

    frame_number: int
    timestamp_seconds: float
    bbox: BoundingBox


@dataclass(frozen=True)
class MotionEventResult:
    """One contiguous span of detected motion across sampled frames.

    Motion detection answers "did something change here", never "what" or
    "who" -- `regions` are plain rectangles, not object classifications.
    """

    start_time_seconds: float
    end_time_seconds: float
    regions: list[MotionRegion] = field(default_factory=list)
    score: float = 0.0
