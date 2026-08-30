"""
API routes for physical evidence chain of custody / QR handoff (Phase
21, Part A).

Every mutating route depends on `app.api.deps.get_current_user` --
identity always comes from an authenticated bearer token, never from a
caller-supplied field in the request body (task Phase 21 scope: "Custody
must never trust a caller-supplied arbitrary string... as proof of
identity"). Business logic lives entirely in `app.core.custody_manager.
CustodyManager`; routes only translate HTTP <-> manager calls and map
`ValueError`/`PermissionError` to 400/403.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.custody_manager import CustodyManager
from app.core.evidence_manager import EvidenceManager
from app.models import CustodyTransfer, User
from app.schemas.custody import (
    CustodyTransferResponse,
    HandoffTokenRequest,
    InitiateHandoffRequest,
    InitiateHandoffResponse,
    RecordIntakeRequest,
)
from app.security import generate_qr_png_base64
from app.storage.db import get_db

router = APIRouter()


def _transfer_response(transfer: CustodyTransfer) -> CustodyTransferResponse:
    return CustodyTransferResponse(
        id=transfer.id,
        evidence_id=transfer.evidence_id,
        transfer_type=transfer.transfer_type.value,
        status=transfer.status.value,
        releasing_user_id=transfer.releasing_user_id,
        releasing_user_display_name=(
            transfer.releasing_user.display_name if transfer.releasing_user else None
        ),
        receiving_user_id=transfer.receiving_user_id,
        receiving_user_display_name=transfer.receiving_user.display_name,
        initiated_at=transfer.initiated_at,
        expires_at=transfer.expires_at,
        accepted_at=transfer.accepted_at,
        location=transfer.location,
        notes=transfer.notes,
        provenance_event_id=transfer.provenance_event_id,
    )


def _require_evidence(db: Session, evidence_id: int) -> None:
    if EvidenceManager.get_evidence(db, evidence_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with id {evidence_id} not found",
        )


def _require_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {user_id} not found"
        )
    return user


@router.post(
    "/evidence/{evidence_id}/custody/intake",
    response_model=CustodyTransferResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_intake(
    evidence_id: int,
    payload: RecordIntakeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustodyTransferResponse:
    """Record the initial physical custody intake of an evidence item."""
    _require_evidence(db, evidence_id)
    receiving_user = _require_user(db, payload.receiving_user_id)
    try:
        transfer = CustodyManager.record_initial_custody(
            db,
            evidence_id=evidence_id,
            receiving_user=receiving_user,
            location=payload.location,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _transfer_response(transfer)


@router.post(
    "/evidence/{evidence_id}/custody/handoff",
    response_model=InitiateHandoffResponse,
    status_code=status.HTTP_201_CREATED,
)
def initiate_handoff(
    evidence_id: int,
    payload: InitiateHandoffRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InitiateHandoffResponse:
    """Initiate a new QR custody handoff. Only the evidence's current
    custodian (the authenticated caller) may successfully call this."""
    _require_evidence(db, evidence_id)
    receiving_user = _require_user(db, payload.receiving_user_id)
    try:
        issued = CustodyManager.initiate_handoff(
            db,
            evidence_id=evidence_id,
            initiator=current_user,
            receiving_user=receiving_user,
            location=payload.location,
            notes=payload.notes,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return InitiateHandoffResponse(
        transfer=_transfer_response(issued.transfer),
        token=issued.raw_token,
        qr_code_png_base64=generate_qr_png_base64(issued.raw_token),
    )


@router.post("/custody/handoff/inspect", response_model=CustodyTransferResponse)
def inspect_pending_handoff(
    payload: HandoffTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustodyTransferResponse:
    """Inspect the pending handoff a scanned QR token refers to, before
    deciding to accept or reject it. Only the intended receiver may
    inspect it."""
    try:
        transfer = CustodyManager.inspect_pending_by_token(
            db, raw_token=payload.token, viewer=current_user
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _transfer_response(transfer)


@router.post("/custody/handoff/accept", response_model=CustodyTransferResponse)
def accept_handoff(
    payload: HandoffTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustodyTransferResponse:
    """Explicitly accept a pending QR handoff. Scanning alone never
    transfers custody -- only this explicit call does."""
    try:
        transfer = CustodyManager.accept_handoff(
            db, raw_token=payload.token, accepting_user=current_user
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _transfer_response(transfer)


@router.post("/custody/handoff/reject", response_model=CustodyTransferResponse)
def reject_handoff(
    payload: HandoffTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustodyTransferResponse:
    """Explicitly reject a pending QR handoff. Only the intended receiver
    may reject it; custody remains unchanged."""
    try:
        transfer = CustodyManager.reject_handoff(
            db, raw_token=payload.token, rejecting_user=current_user
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _transfer_response(transfer)


@router.post("/custody/handoff/{transfer_id}/cancel", response_model=CustodyTransferResponse)
def cancel_handoff(
    transfer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustodyTransferResponse:
    """Cancel a still-pending handoff. Only the user who initiated it may
    cancel it."""
    try:
        transfer = CustodyManager.cancel_handoff(
            db, transfer_id=transfer_id, cancelling_user=current_user
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _transfer_response(transfer)


@router.get("/evidence/{evidence_id}/custody/history", response_model=list[CustodyTransferResponse])
def get_custody_history(
    evidence_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CustodyTransferResponse]:
    """Read-only, chronological custody history for one evidence item."""
    _require_evidence(db, evidence_id)
    history = CustodyManager.get_custody_history(db, evidence_id)
    return [_transfer_response(t) for t in history]


@router.get(
    "/evidence/{evidence_id}/custody/current", response_model=CustodyTransferResponse | None
)
def get_current_custodian(
    evidence_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustodyTransferResponse | None:
    """The evidence item's current custodian, derived from custody
    history (the latest ACCEPTED transfer) -- never a cached field."""
    _require_evidence(db, evidence_id)
    latest = CustodyManager.get_current_custodian_transfer(db, evidence_id)
    if latest is None:
        return None
    return _transfer_response(latest)
