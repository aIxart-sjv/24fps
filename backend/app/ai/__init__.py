"""
AI analysis layer (Phase 13, Master Specification Section 30 "AI Backend").

Pure, DB-free, HTTP-free package: object detection, face detection, motion
detection, and object tracking as plain functions over frame arrays,
producing the dataclasses in `app.ai.types`. `app.core.ai_manager` is the
DB-aware orchestration layer built on top of this package, mirroring every
prior phase's pure-engine/DB-manager split (Phase 9-12).

AI is an analytical assistive layer (task Phase 13 scope): it never
replaces source recordings, timestamps, camera identity, or evidence
provenance, and nothing in this package's output vocabulary implies
identity confirmation -- see `app.ai.types.Detection`/`Track`.
"""

from __future__ import annotations

from app.ai.types import (
    AnalysisType,
    BoundingBox,
    Detection,
    MotionEventResult,
    MotionRegion,
    Track,
    TrackPoint,
)

__all__ = [
    "AnalysisType",
    "BoundingBox",
    "Detection",
    "MotionEventResult",
    "MotionRegion",
    "Track",
    "TrackPoint",
]
