"""
Pydantic schemas for case API requests and responses.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.case import CaseStatus


class CaseCreateRequest(BaseModel):
    """Request to create a new case."""

    case_id: str = Field(..., description="Unique case identifier", min_length=1, max_length=64)
    case_number: str | None = Field(None, description="Case number")
    name: str = Field(..., description="Case name", min_length=1, max_length=256)
    description: str | None = Field(None, description="Case description")
    examiner: str | None = Field(None, description="Examiner name")
    reference_time: datetime | None = Field(None, description="Reference time for the case")


class CaseUpdateRequest(BaseModel):
    """Request to update an existing case."""

    name: str | None = Field(None, description="Case name")
    description: str | None = Field(None, description="Case description")
    examiner: str | None = Field(None, description="Examiner name")
    status: CaseStatus | None = Field(None, description="Case status")
    reference_time: datetime | None = Field(None, description="Reference time for the case")


class CaseResponse(BaseModel):
    """Response containing case information."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: str
    case_number: str | None
    name: str
    description: str | None
    examiner: str | None
    created_at: datetime
    updated_at: datetime
    reference_time: datetime | None
    status: CaseStatus
    software_version: str | None
    schema_version: str | None
