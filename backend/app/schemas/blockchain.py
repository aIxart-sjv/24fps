"""
Pydantic schemas for blockchain anchoring (Phase 17).
Master Specification Section 46 (API Design), `BLOCKCHAIN` section:
`POST /api/v1/cases/{case_id}/blockchain/anchor`,
`GET /api/v1/cases/{case_id}/blockchain/anchors`,
`POST /api/v1/blockchain/verify`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AnchorCreateRequest(BaseModel):
    """Request body for creating a blockchain anchor. All fields
    optional -- most anchors need nothing beyond the case in the URL."""

    reason: str | None = None


class BlockchainAnchorResponse(BaseModel):
    """One persisted blockchain anchor."""

    id: int
    case_id: int
    chain_id: str
    audit_state_hash: str
    provider: str
    network: str
    transaction_reference: str
    status: str
    reason: str | None
    error: str | None
    created_at: datetime
    verified_at: datetime | None


class AnchorVerifyRequest(BaseModel):
    """Request body for `POST /api/v1/blockchain/verify`. Case-agnostic
    at the URL level -- the anchor identifies its own case."""

    anchor_id: int


class ChainFailureDetail(BaseModel):
    """Where and why the local Phase 16 chain first failed, when it did.
    Absent (`null`) when the local chain currently verifies."""

    event_id: int | None
    reason: str
    detail: str


class AnchorVerifyResponse(BaseModel):
    """Structured result of verifying one blockchain anchor."""

    valid: bool
    outcome: str
    anchor_id: int
    case_id: int
    expected_hash: str | None
    anchored_hash: str | None
    chain_valid: bool
    chain_failure: ChainFailureDetail | None
    provider: str
    network: str
    transaction_reference: str
    checked_at: datetime
    detail: str
