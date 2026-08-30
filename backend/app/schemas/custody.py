"""
Pydantic schemas for physical evidence chain of custody / QR handoff
(Phase 21, Part A).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CustodyTransferResponse(BaseModel):
    """One custody transfer row -- never exposes `token_hash` (only the
    raw token, returned once at initiation, is ever meaningful to a
    caller; the hash is an internal storage detail)."""

    id: int
    evidence_id: int
    transfer_type: str
    status: str
    releasing_user_id: int | None
    releasing_user_display_name: str | None
    receiving_user_id: int
    receiving_user_display_name: str
    initiated_at: datetime
    expires_at: datetime | None
    accepted_at: datetime | None
    location: str | None
    notes: str | None
    provenance_event_id: int | None


class InitiateHandoffRequest(BaseModel):
    """Request to start a new QR custody handoff. `receiving_user_id`
    identifies an existing authenticated `User` row -- never a
    caller-supplied free-text name."""

    receiving_user_id: int
    location: str | None = None
    notes: str | None = None


class InitiateHandoffResponse(BaseModel):
    """The newly created PENDING transfer, plus the one-time raw QR
    token (`token`) and a base64-encoded PNG of the QR code image
    encoding only that opaque token -- never evidence metadata or any
    credential."""

    transfer: CustodyTransferResponse
    token: str
    qr_code_png_base64: str


class RecordIntakeRequest(BaseModel):
    """Request to record the initial custody intake of an evidence item."""

    receiving_user_id: int
    location: str | None = None
    notes: str | None = None


class HandoffTokenRequest(BaseModel):
    """A raw QR token presented by a scanning receiver -- the only piece
    of QR content this API ever accepts."""

    token: str
