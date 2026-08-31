"""
Pydantic schemas for recovery results (Master Specification Section 50,
`TABLE: recovery_results`).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecoveryResultResponse(BaseModel):
    """Response containing one recovery attempt's full outcome."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: int
    recording_id: int
    artifact_id: int | None
    method: str
    status: str
    fragments_found: int | None
    fragments_used: int | None
    fragments_missing: int | None
    frames_expected: int | None
    frames_recovered: int | None
    recovery_rate: float | None
    timestamp_error: float | None
    frame_continuity: float | None
    confidence: float | None
    source_offset: int | None
    source_length: int | None
    recovery_engine_version: str | None
    parser_version: str | None
    notes: str | None
    created_at: datetime
    #: A structured, prominent caution -- separate from `notes`'s
    #: per-layer debug trace -- non-`None` exactly when this result's
    #: method/status combination is the framework-only, unvalidated
    #: deleted-record-recovery path (`app.adapters.cp_plus.recovery.
    #: DELETED_RECOVERY_NOT_VALIDATED_STATEMENT`). Phase 24 task scope,
    #: "Recovery UI -- Honest Status": this must never be buried
    #: indistinguishably among routine per-layer notes.
    validation_warning: str | None = None
