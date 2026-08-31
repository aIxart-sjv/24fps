"""
API routes for provenance / chain-of-custody (Phase 15) and the
hash-linked audit chain (Phase 16).
Master Specification Section 46 (API Design), `AUDIT/CUSTODY` section:
`GET /api/v1/cases/{case_id}/audit`, `GET /api/v1/evidence/{evidence_id}/custody`,
`GET /api/v1/cases/{case_id}/audit/verify`.

`POST /api/v1/cases/{case_id}/audit/anchor` (also listed in Section 46) is
explicitly Phase 17 (blockchain anchoring) territory and is not
implemented here.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_case_access, require_case_access_for_evidence
from app.core.audit_chain_manager import AuditChainManager
from app.core.provenance_manager import ProvenanceManager
from app.models import Case, Evidence, ProcessingEvent
from app.schemas.audit import (
    ChainFailureResponse,
    ChainVerificationResponse,
    ProcessingEventResponse,
)
from app.storage.db import get_db

router = APIRouter()


def _event_response(event: ProcessingEvent) -> ProcessingEventResponse:
    return ProcessingEventResponse(
        id=event.id,
        case_id=event.case_id,
        evidence_id=event.evidence_id,
        job_id=event.job_id,
        operation=event.operation,
        actor=event.actor,
        actor_type=event.actor_type,
        tool=event.tool,
        tool_version=event.tool_version,
        software_version=event.software_version,
        parameters=json.loads(event.parameters) if event.parameters else None,
        input_artifact_ids=(
            json.loads(event.input_artifact_ids) if event.input_artifact_ids else None
        ),
        output_artifact_ids=(
            json.loads(event.output_artifact_ids) if event.output_artifact_ids else None
        ),
        started_at=event.started_at,
        completed_at=event.completed_at,
        status=event.status,
        warnings=json.loads(event.warnings) if event.warnings else None,
        error=event.error,
        notes=event.notes,
        description=event.description,
        location_reference=event.location_reference,
        previous_hash=event.previous_hash,
        current_hash=event.current_hash,
        created_at=event.created_at,
    )


@router.get("/cases/{case_id}/audit", response_model=list[ProcessingEventResponse])
def get_case_audit(
    case_id: int,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[ProcessingEventResponse]:
    """List a case's full recorded processing history, in the order recorded."""
    del case
    events = ProvenanceManager.get_case_history(db, case_id)
    return [_event_response(e) for e in events]


@router.get("/evidence/{evidence_id}/custody", response_model=list[ProcessingEventResponse])
def get_evidence_custody(
    evidence_id: int,
    db: Session = Depends(get_db),
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> list[ProcessingEventResponse]:
    """List the chain-of-custody/processing events recorded directly against one evidence item."""
    del evidence
    events = ProvenanceManager.get_evidence_processing_events(db, evidence_id)
    return [_event_response(e) for e in events]


@router.get("/cases/{case_id}/audit/verify", response_model=ChainVerificationResponse)
def verify_case_audit_chain(
    case_id: int,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> ChainVerificationResponse:
    """Verify a case's hash-linked audit chain (Phase 16). Reports where
    the chain first fails, if it does -- never a bare pass/fail."""
    del case
    result = AuditChainManager.verify_case_chain(db, case_id)
    failure = (
        ChainFailureResponse(
            event_id=result.failure.event_id,
            reason=result.failure.reason.value,
            detail=result.failure.detail,
        )
        if result.failure is not None
        else None
    )
    return ChainVerificationResponse(
        case_id=result.case_id if result.case_id is not None else case_id,
        chain_scope=result.chain_scope,
        valid=result.valid,
        event_count=result.event_count,
        first_event_id=result.first_event_id,
        last_event_id=result.last_event_id,
        failure=failure,
    )
