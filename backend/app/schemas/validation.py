"""
Pydantic schemas for the validation/ground-truth layer (Phase 14).
Master Specification Section 46 (API Design), `VALIDATION` section:
`POST /api/v1/validation/jobs`, `GET /api/v1/cases/{case_id}/validation`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.job import JobResponse


class BoundingBoxInput(BaseModel):
    """A ground-truth bounding box, in pixel coordinates."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float


class GroundTruthCreateRequest(BaseModel):
    """Request to create one independently-supplied ground-truth record.

    `source_reference` should describe how/by whom this fact was
    independently established (e.g. "examiner annotation",
    "controlled recording script") -- never "copied from AI output".
    """

    case_id: int = Field(..., description="Primary key of the owning case")
    dataset_id: str = Field(..., description="Scenario/experiment grouping key", min_length=1)
    event_type: str = Field(
        ...,
        description=(
            "One of: object_detection, face_detection, motion, tracking, "
            "timeline, correlation, recovery, vendor_parser"
        ),
    )
    recording_id: Annotated[int | None, Field(description="Related recording, if any")] = None
    camera_id: Annotated[str | None, Field(description="Related camera, if any")] = None
    object_class: Annotated[str | None, Field(description="Expected object/face class")] = None
    timestamp: Annotated[datetime | None, Field(description="Expected timestamp")] = None
    frame_number: Annotated[int | None, Field(description="Expected frame number")] = None
    bbox: Annotated[BoundingBoxInput | None, Field(description="Expected bounding box")] = None
    expected_start: Annotated[datetime | None, Field(description="Expected interval start")] = None
    expected_end: Annotated[datetime | None, Field(description="Expected interval end")] = None
    expected_duration_ms: Annotated[int | None, Field(description="Expected duration")] = None
    expected_frames: Annotated[int | None, Field(description="Expected frame count")] = None
    expected_fragments: Annotated[int | None, Field(description="Expected fragment count")] = None
    expected_hash: Annotated[str | None, Field(description="Expected content hash")] = None
    group_reference: Annotated[
        str | None, Field(description="Groups this row into one expected track/sequence")
    ] = None
    source_reference: Annotated[
        str | None, Field(description="How/by whom this fact was independently established")
    ] = None
    notes: Annotated[str | None, Field(description="Free-text notes")] = None


class GroundTruthResponse(BaseModel):
    """One persisted ground-truth record."""

    id: int
    case_id: int
    dataset_id: str
    recording_id: int | None
    camera_id: str | None
    event_type: str
    object_class: str | None
    timestamp: datetime | None
    frame_number: int | None
    bbox: BoundingBoxInput | None
    expected_start: datetime | None
    expected_end: datetime | None
    expected_duration_ms: int | None
    expected_frames: int | None
    expected_fragments: int | None
    expected_hash: str | None
    group_reference: str | None
    source_reference: str | None
    notes: str | None
    created_at: datetime


class ValidationRunRequest(BaseModel):
    """Request to run one validation job against a ground-truth dataset."""

    case_id: int = Field(..., description="Primary key of the owning case")
    validation_type: str = Field(
        ...,
        description=(
            "One of: object_detection, face_detection, motion, tracking, "
            "timeline, correlation, recovery, vendor_parser"
        ),
    )
    dataset_id: str = Field(..., description="Ground-truth dataset/scenario to validate against")
    iou_threshold: Annotated[
        float, Field(description="Object/face detection bounding-box match threshold", gt=0, le=1)
    ] = 0.5
    require_class_match: Annotated[
        bool, Field(description="Require exact class agreement for detection matching")
    ] = True
    motion_overlap_threshold: Annotated[
        float, Field(description="Motion-event temporal-IoU match threshold", gt=0, le=1)
    ] = 0.3
    correlation_time_tolerance_seconds: Annotated[
        float, Field(description="Correlation sequence per-event timestamp tolerance", gt=0)
    ] = 5.0
    frame_overlap_tolerance: Annotated[
        int, Field(description="Tracking frame-range overlap slack", ge=0)
    ] = 0


class ValidationMetricResponse(BaseModel):
    """One persisted named metric produced by a validation run."""

    id: int
    job_id: int
    case_id: int
    dataset_id: str
    validation_type: str
    metric_name: str
    metric_value: float | None
    numerator: float | None
    denominator: float | None
    threshold: float | None
    notes: str | None
    created_at: datetime


class ValidationRunResponse(BaseModel):
    """The full outcome of one validation run: the job plus every metric it produced."""

    job: JobResponse
    metrics: list[ValidationMetricResponse]
