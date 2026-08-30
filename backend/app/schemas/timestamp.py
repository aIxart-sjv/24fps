"""
Pydantic schemas for timestamp normalization (Phase 11).
Master Specification Section 46 (API Design), `TIMELINE` section:
`POST /api/v1/timestamps/normalize`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class TimestampReferenceRequest(BaseModel):
    """An examiner-supplied external reference timestamp (task Phase 11
    scope, section 8) — a plain value, not a new trusted-time subsystem."""

    reference_timestamp: datetime = Field(
        ..., description="The independently-sourced reference timestamp"
    )
    reference_timezone: Annotated[
        str | None,
        Field(
            description=(
                "IANA timezone name to interpret reference_timestamp under, if it is naive. "
                "Not required when reference_timestamp already carries timezone info."
            )
        ),
    ] = None
    reference_source: str = Field(
        ...,
        description='Where the reference came from (e.g. "examiner-recorded event time")',
        min_length=1,
    )
    reference_basis: str = Field(
        ...,
        description="Why this reference is trusted to correspond to the same real-world instant",
        min_length=1,
    )
    method: Annotated[
        str,
        Field(
            description=(
                "Which Master Specification Section 27 normalization method this reference "
                "represents: explicit_dvr_clock_comparison, known_external_event, "
                "system_reference_time, or manual_examiner_adjustment"
            )
        ),
    ] = "explicit_dvr_clock_comparison"


class TimestampNormalizeRequest(BaseModel):
    """Request to normalize one recording's original timestamps."""

    recording_id: int = Field(..., description="Primary key of the Recording to normalize")
    source_timezone: Annotated[
        str | None,
        Field(
            description=(
                "IANA timezone name to interpret the recording's naive original timestamps "
                'under (e.g. "Asia/Kolkata"). Examiner-supplied — never inferred.'
            )
        ),
    ] = None
    source_timezone_basis: Annotated[
        str | None, Field(description="Provenance for source_timezone (e.g. a device fact sheet)")
    ] = None
    reference: Annotated[
        TimestampReferenceRequest | None,
        Field(description="An external reference pair to compute a verified clock offset from"),
    ] = None


class TimestampNormalizeResponse(BaseModel):
    """Result of one normalization attempt (task Phase 11 scope, section 19 —
    every question about provenance answered in one place)."""

    model_config = ConfigDict(from_attributes=True)

    recording_id: int
    overall_status: str
    source: str
    start_original: datetime | None
    end_original: datetime | None
    start_normalized: datetime | None
    end_normalized: datetime | None
    start_status: str
    end_status: str
    start_reason: str
    end_reason: str
    source_timezone: str | None
    source_timezone_basis: str | None
    offset_seconds: float | None
    method: str
