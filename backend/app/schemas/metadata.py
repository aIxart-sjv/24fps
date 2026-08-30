"""
Pydantic schemas for recording metadata (Master Specification Section 50,
`TABLE: metadata`).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RecordingMetadataResponse(BaseModel):
    """One key/value metadata entry attached to a recording."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    recording_id: int
    key: str
    value: str | None
    source: str | None
    confidence: float | None
