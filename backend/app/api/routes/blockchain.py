"""
API routes for blockchain anchoring (Phase 17).
Master Specification Section 46 (API Design), `BLOCKCHAIN` section:
`POST /api/v1/cases/{case_id}/blockchain/anchor`,
`GET /api/v1/cases/{case_id}/blockchain/anchors`,
`POST /api/v1/blockchain/verify`.

Only these three documented routes are implemented -- no speculative
additions (task Phase 17 scope section 21).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_case_access
from app.blockchain.provider import AnchorSubmissionError, BlockchainProviderNotConfiguredError
from app.core.blockchain_manager import BlockchainManager, ChainNotValidForAnchoringError
from app.core.case_authorization_service import CaseAccessDeniedError, CaseAuthorizationService
from app.models import BlockchainAnchor, Case, User
from app.schemas.blockchain import (
    AnchorCreateRequest,
    AnchorVerifyRequest,
    AnchorVerifyResponse,
    BlockchainAnchorResponse,
    ChainFailureDetail,
)
from app.storage.db import get_db

router = APIRouter()


def _anchor_response(anchor: BlockchainAnchor) -> BlockchainAnchorResponse:
    return BlockchainAnchorResponse(
        id=anchor.id,
        case_id=anchor.case_id,
        chain_id=anchor.chain_id,
        audit_state_hash=anchor.audit_state_hash,
        provider=anchor.provider,
        network=anchor.network,
        transaction_reference=anchor.transaction_reference,
        status=anchor.status,
        reason=anchor.reason,
        error=anchor.error,
        created_at=anchor.created_at,
        verified_at=anchor.verified_at,
    )


@router.post("/cases/{case_id}/blockchain/anchor", response_model=BlockchainAnchorResponse)
def create_blockchain_anchor(
    case_id: int,
    body: AnchorCreateRequest,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> BlockchainAnchorResponse:
    """Anchor a case's current, verified Phase 16 audit chain state."""
    del case
    try:
        anchor = BlockchainManager.create_anchor(db, case_id=case_id, reason=body.reason)
    except ChainNotValidForAnchoringError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except BlockchainProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except AnchorSubmissionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return _anchor_response(anchor)


@router.get("/cases/{case_id}/blockchain/anchors", response_model=list[BlockchainAnchorResponse])
def list_blockchain_anchors(
    case_id: int,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[BlockchainAnchorResponse]:
    """List every anchor ever recorded for a case, oldest first. Never
    just "the latest" -- every prior anchor is retained."""
    del case
    anchors = BlockchainManager.list_anchors(db, case_id)
    return [_anchor_response(a) for a in anchors]


@router.post("/blockchain/verify", response_model=AnchorVerifyResponse)
def verify_blockchain_anchor(
    body: AnchorVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnchorVerifyResponse:
    """Verify a recorded anchor against the case's current local chain state.

    Not a `require_case_access`-style path-param dependency (there is no
    `case_id` path segment to key one on -- only an opaque `anchor_id` in
    the body), so this resolves the anchor's owning case afterward and
    authorizes against that instead. The response includes real case
    state (`case_id`, hash values), so an anchor ID alone must not be
    enough to read it -- same IDOR concern task section 18 names for
    every other case-scoped resource.
    """
    try:
        result = BlockchainManager.verify_anchor(db, anchor_id=body.anchor_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if result.case_id is not None:
        try:
            CaseAuthorizationService.require_case_access(db, current_user, result.case_id)
        except CaseAccessDeniedError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    chain_failure = (
        ChainFailureDetail(
            event_id=result.chain_failure.event_id,
            reason=result.chain_failure.reason.value,
            detail=result.chain_failure.detail,
        )
        if result.chain_failure is not None
        else None
    )
    return AnchorVerifyResponse(
        valid=result.valid,
        outcome=result.outcome.value,
        anchor_id=result.anchor_id,
        case_id=result.case_id,
        expected_hash=result.expected_hash,
        anchored_hash=result.anchored_hash,
        chain_valid=result.chain_valid,
        chain_failure=chain_failure,
        provider=result.provider_name,
        network=result.network,
        transaction_reference=result.transaction_reference,
        checked_at=result.checked_at,
        detail=result.detail,
    )
