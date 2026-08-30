"""
Pydantic schemas for evidence API requests and responses.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCreateRequest(BaseModel):
    """Request to register a new evidence item."""

    evidence_id: str = Field(
        ..., description="Unique evidence identifier", min_length=1, max_length=64
    )
    source_type: str = Field(
        ..., description="Type of evidence source", min_length=1, max_length=64
    )
    source_path: str | None = Field(None, description="Path or reference to the evidence source")
    source_description: str | None = Field(None, description="Description of the evidence source")


class EvidenceResponse(BaseModel):
    """Response containing evidence information."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: str
    case_id: int
    source_type: str
    source_path: str | None
    source_description: str | None
    status: str
    created_at: datetime
    updated_at: datetime
