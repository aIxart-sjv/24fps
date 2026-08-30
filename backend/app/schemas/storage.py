"""
Pydantic schemas for storage device information responses.
Master Specification Section 50 (storage_devices table).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StorageResponse(BaseModel):
    """Response containing storage device information."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    capacity_bytes: int | None
    sector_size: int | None
    interface: str | None
    image_format: str | None
    image_path: str | None
    read_only: bool | None
    status: str | None
