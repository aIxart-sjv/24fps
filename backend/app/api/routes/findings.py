"""
API routes for the findings review inbox (Phase 22).
Master Specification Section 57's orchestrator output; task Phase 22
scope, "API": `GET /cases/{case_id}/findings`, `GET /findings/{finding_id}`,
`PATCH /findings/{finding_id}`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_case_access, require_case_access_for_finding
from app.core.findings_engine import FindingsEngine
from app.models import (
    AIResult,
    Case,
    Finding,
    FindingStatus,
    Recording,
    RecoveryResult,
    TimelineEvent,
    User,
)
from app.schemas.finding import FindingResponse, FindingUpdateRequest
from app.storage.db import get_db

router = APIRouter()


def _resolve_finding_location(db: Session, finding: Finding) -> tuple[int | None, datetime | None]:
    """Resolve `(recording_id, timestamp)` for a finding -- never a
    fabricated value, only what a directly-referenced result already
    establishes. See `FindingResponse.resolved_recording_id`'s docstring
    for the resolution order."""
    if finding.recording_id is not None:
        recording = db.query(Recording).filter(Recording.id == finding.recording_id).first()
        timestamp = (recording.start_normalized or recording.start_original) if recording else None
        return finding.recording_id, timestamp

    reference: dict[str, object] = (
        json.loads(finding.source_reference) if finding.source_reference else {}
    )

    ai_job_id = reference.get("ai_job_id")
    if isinstance(ai_job_id, int):
        first_result = (
            db.query(AIResult)
            .filter(AIResult.job_id == ai_job_id)
            .order_by(AIResult.frame_number.asc())
            .first()
        )
        if first_result is not None:
            return first_result.recording_id, first_result.timestamp

    correlated_event_ids = reference.get("correlated_event_ids")
    if isinstance(correlated_event_ids, list) and correlated_event_ids:
        first_event = (
            db.query(TimelineEvent)
            .filter(TimelineEvent.id.in_(correlated_event_ids))
            .order_by(TimelineEvent.id.asc())
            .first()
        )
        if first_event is not None and first_event.recording_id is not None:
            return (
                first_event.recording_id,
                first_event.normalized_timestamp or first_event.original_timestamp,
            )

    recovery_result_id = reference.get("recovery_result_id")
    if isinstance(recovery_result_id, int):
        recovery_result = (
            db.query(RecoveryResult).filter(RecoveryResult.id == recovery_result_id).first()
        )
        if recovery_result is not None:
            recording = (
                db.query(Recording).filter(Recording.id == recovery_result.recording_id).first()
            )
            if recording is not None:
                return (
                    recovery_result.recording_id,
                    recording.start_normalized or recording.start_original,
                )

    return None, None


def _finding_response(db: Session, finding: Finding) -> FindingResponse:
    resolved_recording_id, resolved_timestamp = _resolve_finding_location(db, finding)
    return FindingResponse(
        id=finding.id,
        case_id=finding.case_id,
        evidence_id=finding.evidence_id,
        recording_id=finding.recording_id,
        source_job_id=finding.source_job_id,
        finding_type=finding.finding_type,
        severity=finding.severity,
        confidence=finding.confidence,
        title=finding.title,
        description=finding.description,
        status=finding.status,
        source_reference=json.loads(finding.source_reference) if finding.source_reference else None,
        limitations=json.loads(finding.limitations) if finding.limitations else None,
        occurrence_count=finding.occurrence_count,
        created_at=finding.created_at,
        updated_at=finding.updated_at,
        resolved_at=finding.resolved_at,
        resolved_by=finding.resolved_by,
        resolution_notes=finding.resolution_notes,
        resolved_recording_id=resolved_recording_id,
        resolved_timestamp=resolved_timestamp,
    )


@router.get("/cases/{case_id}/findings", response_model=list[FindingResponse])
def list_case_findings(
    case_id: int,
    status_filter: str | None = None,
    severity: str | None = None,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[FindingResponse]:
    """List a case's findings, most urgent/unresolved first (deterministic
    priority order -- see `FindingsEngine.list_case_findings`'s docstring)."""
    del case
    findings = FindingsEngine.list_case_findings(
        db, case_id, status=status_filter, severity=severity
    )
    return [_finding_response(db, f) for f in findings]


@router.get("/findings/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding: Finding = Depends(require_case_access_for_finding),
    db: Session = Depends(get_db),
) -> FindingResponse:
    """Retrieve one finding by ID."""
    return _finding_response(db, finding)


@router.patch("/findings/{finding_id}", response_model=FindingResponse)
def update_finding(
    request: FindingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    finding: Finding = Depends(require_case_access_for_finding),
) -> FindingResponse:
    """Move a finding through its reviewable lifecycle (task Phase 22
    scope, "Finding Lifecycle") -- never deletes it. The examiner remains
    responsible for interpretation; this endpoint only records that
    review happened, not any conclusion about the underlying evidence."""
    try:
        new_status = FindingStatus(request.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unrecognized finding status: {request.status!r}",
        ) from exc

    finding.status = new_status.value
    if request.resolution_notes is not None:
        finding.resolution_notes = request.resolution_notes
    if new_status in (FindingStatus.RESOLVED, FindingStatus.DISMISSED):
        finding.resolved_at = datetime.now(UTC)
        finding.resolved_by = request.resolved_by or current_user.display_name
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return _finding_response(db, finding)
