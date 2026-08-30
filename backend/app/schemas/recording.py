"""
Pydantic schemas for recording information responses.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecordingResponse(BaseModel):
    """Response containing recording information."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    recording_id: str
    camera_id: str | None
    channel: int | None
    start_original: datetime | None
    end_original: datetime | None
    start_normalized: datetime | None
    end_normalized: datetime | None
    duration_ms: int | None
    codec: str | None
    container: str | None
    width: int | None
    height: int | None
    fps: float | None
    source_location: str | None
    recovery_status: str | None
    recovery_method: str | None
    confidence: float | None
    artifact_id: str | None


class RecordingSessionLinkRequest(BaseModel):
    """Request to link an ordered sequence of segment evidence items into one session."""

    evidence_ids: list[int] = Field(
        ...,
        description=(
            "Primary keys of the segment evidence items, in caller-asserted playback order "
            "(e.g. the export filenames' own start timestamps). Not reordered by the backend."
        ),
        min_length=2,
    )
