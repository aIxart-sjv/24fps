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

from app.api.deps import get_current_user
from app.core.case_manager import CaseManager
from app.core.findings_engine import FindingsEngine
from app.models import Finding, FindingStatus, User
from app.schemas.finding import FindingResponse, FindingUpdateRequest
from app.storage.db import get_db

router = APIRouter()


def _finding_response(finding: Finding) -> FindingResponse:
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
    )


@router.get("/cases/{case_id}/findings", response_model=list[FindingResponse])
def list_case_findings(
    case_id: int,
    status_filter: str | None = None,
    severity: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FindingResponse]:
    """List a case's findings, most urgent/unresolved first (deterministic
    priority order -- see `FindingsEngine.list_case_findings`'s docstring)."""
    if CaseManager.get_case(db, case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Case with id {case_id} not found"
        )
    findings = FindingsEngine.list_case_findings(db, case_id, status=status_filter, severity=severity)
    return [_finding_response(f) for f in findings]


@router.get("/findings/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FindingResponse:
    """Retrieve one finding by ID."""
    finding = FindingsEngine.get_finding(db, finding_id)
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Finding with id {finding_id} not found"
        )
    return _finding_response(finding)


@router.patch("/findings/{finding_id}", response_model=FindingResponse)
def update_finding(
    finding_id: int,
    request: FindingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FindingResponse:
    """Move a finding through its reviewable lifecycle (task Phase 22
    scope, "Finding Lifecycle") -- never deletes it. The examiner remains
    responsible for interpretation; this endpoint only records that
    review happened, not any conclusion about the underlying evidence."""
    finding = FindingsEngine.get_finding(db, finding_id)
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Finding with id {finding_id} not found"
        )
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
    return _finding_response(finding)
