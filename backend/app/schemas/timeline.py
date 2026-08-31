"""
Pydantic schemas for timeline events and cross-camera correlation
(Phase 12). Master Specification Section 46 (API Design), `CORRELATION`
section: `POST /cases/{case_id}/correlation/run`,
`GET /cases/{case_id}/correlation/events`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class TimelineEventResponse(BaseModel):
    """One timeline event (a source event, or a persisted correlation result)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    recording_id: int | None
    camera_id: str | None
    event_type: str
    original_timestamp: datetime | None
    normalized_timestamp: datetime | None
    confidence: float | None
    source: str | None
    description: str | None
    ai_reference: str | None
    recovery_status: str | None
    correlation_id: int | None
    created_at: datetime
    #: `app.timeline.NormalizationStatus` value (`"verified"`/
    #: `"unverified"`/`"partial"`/`"unknown"`) from the linked recording's
    #: own `TimestampManager.normalize_recording` run -- `"unknown"` when
    #: this event has no linked recording (e.g. an examiner marker) or
    #: normalization has not run yet, never a stronger claim than that
    #: (Phase 24 task scope, "Timeline -- Fix Current Presentation").
    timestamp_status: str
    #: `app.timeline.TimestampSource` value (e.g. `"filename_derived"`),
    #: or `None` when not applicable/not yet computed.
    timestamp_source: str | None
    #: Whether an examiner-supplied source timezone was ever recorded for
    #: the linked recording -- `"known"` or `"unknown"`, never fabricated
    #: as resolved when no timezone was actually supplied.
    timezone_status: str
    #: Free-text provenance for the timezone (e.g. "case device fact
    #: sheet: NVR configured for IST"), or `None` when `timezone_status`
    #: is `"unknown"`.
    timezone_basis: str | None


class ExaminerMarkerCreateRequest(BaseModel):
    """Request to record an examiner-entered/external shared event marker.

    Kept explicitly identified as manual/external (task Phase 12 scope:
    "Do not convert an examiner marker into objective source evidence.")
    — always persisted with `event_type="examiner_marker"` and
    `source="examiner"`, never claimed as a device/vendor timestamp.
    """

    case_id: int = Field(..., description="Primary key of the case this marker belongs to")
    camera_id: Annotated[str | None, Field(description="Camera this marker relates to, if any")] = (
        None
    )
    recording_id: Annotated[
        int | None, Field(description="Recording this marker relates to, if any")
    ] = None
    timestamp: datetime = Field(..., description="The examiner-supplied timestamp for this marker")
    description: str = Field(..., description="What the marker records", min_length=1)


class CameraTransitionInput(BaseModel):
    """One directed, examiner-configured camera adjacency edge."""

    from_camera_id: str = Field(..., min_length=1)
    to_camera_id: str = Field(..., min_length=1)
    expected_movement: Annotated[
        str | None,
        Field(description="Optional expected movement-direction label for this transition"),
    ] = None


class CorrelationRunRequest(BaseModel):
    """Request to run correlation over a case's current timeline events."""

    topology: Annotated[
        list[CameraTransitionInput] | None,
        Field(
            description=(
                "Explicit, examiner-configured camera adjacency. Never inferred from camera "
                "numbering — omit entirely to report topology as unavailable."
            )
        ),
    ] = None
    max_gap_seconds: Annotated[
        float | None,
        Field(
            description="Temporal correlation window in seconds. Defaults to DEFAULT_MAX_GAP_SECONDS.",
            gt=0,
        ),
    ] = None


class PairwiseLinkResponse(BaseModel):
    """One edge in a correlation candidate's sequence, with its full signal breakdown."""

    from_event_id: str
    to_event_id: str
    status: str
    temporal: str
    topology: str
    movement: str
    track: str
    gap_seconds: float | None
    confidence: float | None
    confidence_basis: list[str]
    reasons: list[str]
    warnings: list[str]


class CorrelationCandidateResponse(BaseModel):
    """One correlation candidate (an "investigation sequence"), never an identity claim."""

    correlation_event_id: int
    event_ids: list[str]
    status: str
    confidence: float | None
    confidence_basis: list[str]
    recovery_signals: dict[str, str]
    max_gap_seconds: float
    method: str
    warnings: list[str]
    links: list[PairwiseLinkResponse]


class CorrelationRunResponse(BaseModel):
    """Response to a correlation run — the candidates created plus the processing summary."""

    case_id: int
    candidates: list[CorrelationCandidateResponse]
    input_event_count: int
    events_excluded_no_timestamp: int
    duplicate_events_ignored: int
    candidate_pairs_considered: int
    candidates_rejected: int
    max_gap_seconds: float
    topology_configured: bool
    processing_time_seconds: float
