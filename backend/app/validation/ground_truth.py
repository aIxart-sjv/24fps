"""
Plain, DB-free ground-truth dataclasses (Phase 14, task scope sections 3-4).

Decoupled from the persisted `app.models.validation.GroundTruth` ORM row
on purpose: every metric module in `app.validation` takes these plain
types, never an ORM object, so metric math is testable without a
database. `app.core.validation_manager.ValidationManager` converts
persisted `GroundTruth` rows into these before calling the metric
modules.

Ground truth here is always independently supplied by the caller (a
controlled test scenario, an examiner annotation) -- nothing in this
module, or anywhere in `app.validation`, derives a ground-truth value
from a system output. Reuses `app.ai.types.BoundingBox` (Phase 13) rather
than defining a second bounding-box type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.ai.types import BoundingBox

__all__ = [
    "GroundTruthDetection",
    "GroundTruthMotionEvent",
    "GroundTruthRecoverySegment",
    "GroundTruthSequence",
    "GroundTruthSequenceEvent",
    "GroundTruthTrack",
]


@dataclass(frozen=True)
class GroundTruthDetection:
    """One independently-known expected object/face detection.

    `class_name` is a plain label (`"person"`, `"car"`, `"face"`) --
    never an identity, matching `app.ai.types.Detection`'s own
    convention.
    """

    class_name: str
    bbox: BoundingBox
    frame_number: int | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class GroundTruthMotionEvent:
    """One independently-known expected motion event, in absolute time."""

    start_time: datetime
    end_time: datetime


@dataclass(frozen=True)
class GroundTruthTrack:
    """One independently-known expected object track.

    Describes expected continuity of a detected object across frames --
    never an identity (Master Specification Section 32: "Tracking does
    not automatically prove identity.").
    """

    class_name: str
    first_seen_frame: int
    last_seen_frame: int
    expected_frame_count: int | None = None


@dataclass(frozen=True)
class GroundTruthSequenceEvent:
    """One event within an expected cross-camera event sequence."""

    camera_id: str
    timestamp: datetime


@dataclass(frozen=True)
class GroundTruthSequence:
    """One independently-known expected ordered cross-camera sequence
    (the documented A -> B -> C scenario, Master Specification Section
    29). `events` is stored in expected chronological order.
    """

    group_reference: str
    events: list[GroundTruthSequenceEvent] = field(default_factory=list)


@dataclass(frozen=True)
class GroundTruthRecoverySegment:
    """One independently-known expected recovered recording segment
    (Master Specification Section 37's ground-truth test case)."""

    expected_start: datetime | None = None
    expected_end: datetime | None = None
    expected_duration_ms: int | None = None
    expected_frames: int | None = None
    expected_fragments: int | None = None
    expected_hash: str | None = None
