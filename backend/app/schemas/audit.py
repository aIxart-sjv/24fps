"""
Pydantic schemas for provenance / chain-of-custody (Phase 15) and the
hash-linked audit chain (Phase 16).
Master Specification Section 46 (API Design), `AUDIT/CUSTODY` section:
`GET /api/v1/cases/{case_id}/audit`, `GET /api/v1/evidence/{evidence_id}/custody`,
`GET /api/v1/cases/{case_id}/audit/verify`.

`POST /api/v1/cases/{case_id}/audit/anchor` (also listed in Section 46) is
explicitly Phase 17 (blockchain anchoring) territory and has no schema
here.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProcessingEventResponse(BaseModel):
    """One persisted processing/custody event, with its JSON-encoded
    columns decoded to plain Python values (never returned as opaque
    strings)."""

    id: int
    case_id: int
    evidence_id: int | None
    job_id: int | None
    operation: str
    actor: str
    actor_type: str
    tool: str | None
    tool_version: str | None
    software_version: str | None
    parameters: dict[str, object] | None
    input_artifact_ids: list[int] | None
    output_artifact_ids: list[int] | None
    started_at: datetime | None
    completed_at: datetime | None
    status: str
    warnings: list[str] | None
    error: str | None
    notes: str | None
    description: str | None
    location_reference: str | None
    #: Set by Phase 16's `AuditChainManager.seal_event` at creation time.
    previous_hash: str | None
    current_hash: str | None
    created_at: datetime


class ChainFailureResponse(BaseModel):
    """Where and why a hash chain first failed verification. Absent
    (`null`) when the chain is valid."""

    event_id: int | None
    reason: str
    detail: str


class ChainVerificationResponse(BaseModel):
    """Result of verifying one case's hash-linked audit chain."""

    case_id: int
    chain_scope: str
    valid: bool
    event_count: int
    first_event_id: int | None
    last_event_id: int | None
    failure: ChainFailureResponse | None
