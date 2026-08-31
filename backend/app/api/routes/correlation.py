"""
API routes for cross-camera correlation (Phase 12).
Master Specification Section 46 (API Design), `CORRELATION` section:
`POST /cases/{case_id}/correlation/run`, `GET /cases/{case_id}/correlation/events`.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_case_access
from app.core.correlation_manager import CorrelationManager
from app.models import Case, TimelineEvent
from app.schemas.timeline import (
    CorrelationCandidateResponse,
    CorrelationRunRequest,
    CorrelationRunResponse,
    PairwiseLinkResponse,
)
from app.storage.db import get_db
from app.timeline.correlation import CameraTopology

router = APIRouter()


def _candidate_response(event: TimelineEvent) -> CorrelationCandidateResponse:
    """Reconstruct a `CorrelationCandidateResponse` from one persisted `correlated_event` row.

    The full signal breakdown was JSON-encoded into `description` at
    persistence time (`CorrelationManager._persist_candidate`) — decoded
    here, never recomputed.
    """
    details = json.loads(event.description) if event.description else {}
    links = [
        PairwiseLinkResponse(
            from_event_id=link["from_event_id"],
            to_event_id=link["to_event_id"],
            status=link["status"],
            temporal=link["temporal"],
            topology=link["topology"],
            movement=link["movement"],
            track=link["track"],
            gap_seconds=link["gap_seconds"],
            confidence=link["confidence"],
            confidence_basis=link["confidence_basis"],
            reasons=link["reasons"],
            warnings=link["warnings"],
        )
        for link in details.get("links", [])
    ]
    return CorrelationCandidateResponse(
        correlation_event_id=event.id,
        event_ids=details.get("event_ids", []),
        status=details.get("status", "unknown"),
        confidence=event.confidence,
        confidence_basis=details.get("confidence_basis", []),
        recovery_signals=details.get("recovery_signals", {}),
        max_gap_seconds=details.get("max_gap_seconds", 0.0),
        method=details.get("method", ""),
        warnings=details.get("warnings", []),
        links=links,
    )


@router.post("/cases/{case_id}/correlation/run", response_model=CorrelationRunResponse)
def run_correlation(
    case_id: int,
    request: CorrelationRunRequest,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> CorrelationRunResponse:
    """Run cross-camera correlation over a case's current timeline events and persist results.

    This is an ANALYTICAL correlation, never identity confirmation
    (Master Specification Section 29: "an analytical relation, not proof
    of identity"). Camera topology is only ever used if explicitly
    supplied in `request.topology` — never inferred from camera numbering.
    """
    del case

    topology: CameraTopology | None = None
    if request.topology:
        topology = CameraTopology(
            transitions={
                (t.from_camera_id, t.to_camera_id): t.expected_movement for t in request.topology
            }
        )

    result, persisted = CorrelationManager.run_correlation(
        db, case_id, topology=topology, max_gap_seconds=request.max_gap_seconds
    )

    return CorrelationRunResponse(
        case_id=case_id,
        candidates=[_candidate_response(event) for event in persisted],
        input_event_count=result.input_event_count,
        events_excluded_no_timestamp=result.events_excluded_no_timestamp,
        duplicate_events_ignored=result.duplicate_events_ignored,
        candidate_pairs_considered=result.candidate_pairs_considered,
        candidates_rejected=result.candidates_rejected,
        max_gap_seconds=result.max_gap_seconds,
        topology_configured=result.topology_configured,
        processing_time_seconds=result.processing_time_seconds,
    )


@router.get(
    "/cases/{case_id}/correlation/events", response_model=list[CorrelationCandidateResponse]
)
def list_correlation_events(
    case_id: int,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[CorrelationCandidateResponse]:
    """List previously persisted correlation candidates for a case."""
    del case
    events = CorrelationManager.list_correlations(db, case_id)
    return [_candidate_response(event) for event in events]
