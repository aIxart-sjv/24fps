"""
Pydantic schemas for the findings API (Phase 22).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FindingResponse(BaseModel):
    """One structured forensic finding, decoded to plain Python values."""

    id: int
    case_id: int
    evidence_id: int | None
    recording_id: int | None
    source_job_id: int | None
    finding_type: str
    severity: str
    confidence: str
    title: str
    description: str
    status: str
    source_reference: dict[str, object] | None
    limitations: list[str] | None
    occurrence_count: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_notes: str | None


class FindingUpdateRequest(BaseModel):
    """Officer review action on one finding (task Phase 22 scope,
    "Finding Lifecycle"). Only the reviewable fields are mutable --
    everything describing the underlying condition is set exclusively by
    the findings engine."""

    status: str = Field(description="One of FindingStatus's values.")
    resolved_by: str | None = Field(
        default=None, description="Display name of the reviewing officer."
    )
    resolution_notes: str | None = Field(default=None, description="Free-text review notes.")
