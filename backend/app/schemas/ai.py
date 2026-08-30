"""
Pydantic schemas for AI analysis (Phase 13).
Master Specification Section 46 (API Design), `AI` section:
`POST /api/v1/ai/jobs`, `GET /api/v1/cases/{case_id}/ai-results`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class AIJobCreateRequest(BaseModel):
    """Request to run one AI analysis job.

    Every parameter here is recorded verbatim on the created `Job` row
    (task Phase 13 scope: "Persist enough metadata to explain exactly
    what was run").
    """

    case_id: int = Field(..., description="Primary key of the owning case")
    recording_ids: list[int] = Field(..., description="Recordings to process", min_length=1)
    analysis_types: list[str] = Field(
        ...,
        description=("Any of: object_detection, face_detection, motion_detection, object_tracking"),
        min_length=1,
    )
    sampling_strategy: Annotated[str, Field(description="'fps', 'interval', or 'all'")] = "fps"
    sampling_value: Annotated[
        float | None,
        Field(description="Strategy-specific value (target fps, or frame interval)", gt=0),
    ] = None
    confidence_threshold: Annotated[
        float, Field(description="Minimum object-detection/tracking confidence", ge=0, le=1)
    ] = 0.25
    face_confidence_threshold: Annotated[
        float, Field(description="Minimum face-detection score", ge=0, le=1)
    ] = 0.6
    classes: Annotated[list[str] | None, Field(description="Optional object-class allow-list")] = (
        None
    )
    tracker: Annotated[str, Field(description="'bytetrack.yaml' or 'botsort.yaml'")] = (
        "bytetrack.yaml"
    )
    prefer_gpu: Annotated[bool, Field(description="Use CUDA if available")] = True


class BoundingBoxResponse(BaseModel):
    """A detection's bounding box, in pixel coordinates."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float


class AIResultResponse(BaseModel):
    """One persisted object/face detection."""

    id: int
    job_id: int | None
    case_id: int
    recording_id: int
    analysis_type: str
    model_name: str
    model_version: str
    frame_number: int
    timestamp: datetime | None
    class_name: str
    confidence: float
    bbox: BoundingBoxResponse
    track_id: int | None
    source_artifact: int
    created_at: datetime
