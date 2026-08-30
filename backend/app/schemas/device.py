"""
Pydantic schemas for device information responses and Phase 6 identification.
Master Specification Section 13 ("Device Identification").
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DeviceResponse(BaseModel):
    """Response containing device information."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    vendor: str | None
    model: str | None
    firmware: str | None
    serial_number: str | None
    device_type: str | None
    channel_count: int | None
    camera_count: int | None
    network_info: str | None
    confidence: float | None
    identification_method: str | None


class IdentificationStatus(str, Enum):
    """Overall outcome of a Phase 6 identification pass (Master Spec Section 55).

    `UNKNOWN` and `UNSUPPORTED` are both first-class, expected outcomes —
    not errors: `UNKNOWN` means no reliable signal was found at all,
    `UNSUPPORTED` means the evidence declares a recognizable format that
    this environment/build cannot actually process (e.g. E01 without
    libewf installed, or a file that fails its own claimed signature).
    """

    IDENTIFIED = "identified"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class DeviceIdentificationResult(BaseModel):
    """Normalized Phase 6 identification result (Master Spec Section 13).

    This is the single object later phases consume: Phase 7's future
    `select_adapter(device_identification_result)` is expected to read
    `parser_selection_hints`/`storage_format`/`filesystem_type` from
    exactly this shape. It is never persisted as its own table — the
    subset that has a home on the existing `Device`/`Storage` models is
    written there; the rest (warnings, supporting evidence, hints) is
    returned directly by the identification API rather than requiring a
    new migration (Master Specification Section 51, rule 11: unknown
    values must be explicit, not fabricated — so every field here defaults
    to `None`/empty rather than a guessed value).
    """

    status: IdentificationStatus

    vendor: str | None = None
    model: str | None = None
    firmware: str | None = None
    device_type: str | None = None
    serial_number: str | None = None

    storage_format: str | None = None
    filesystem_type: str | None = None
    sector_size: int | None = None
    capacity: int | None = None

    identification_method: str
    confidence: float = Field(..., ge=0.0, le=1.0)

    warnings: list[str] = []
    supporting_evidence: list[str] = []
    parser_selection_hints: list[str] = []
