"""
Pydantic schemas for acquisition-domain requests.
Master Specification Section 9 ("Acquisition Backend").
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NativeExportRegisterRequest(BaseModel):
    """Request to register a native DVR/NVR export as evidence (Path 1).

    `source_type` is intentionally absent: registering through this path
    always pins it to `"native_export"` — see
    `app.acquisition.native_export.NATIVE_EXPORT_SOURCE_TYPE`. Any vendor
    player, logs, or metadata that came with the export should already be
    present alongside it under `source_path` (or referenced in
    `source_description`); this backend does not yet parse them.
    """

    evidence_id: str = Field(
        ..., description="Unique evidence identifier", min_length=1, max_length=64
    )
    source_path: str = Field(
        ..., description="Path to the exported data, relative to EVIDENCE_ROOT", min_length=1
    )
    source_description: str | None = Field(
        None,
        description="Examiner notes on the export, e.g. what vendor player/logs accompany it",
    )
