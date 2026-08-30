"""
Pydantic schemas for evidence integrity hash API responses.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.hash import HashAlgorithm, VerificationStatus


class HashResponse(BaseModel):
    """Response containing a single stored evidence hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    algorithm: HashAlgorithm
    hash_value: str
    calculated_at: datetime
    software_version: str | None
    source_reference: str | None
    verification_status: VerificationStatus
