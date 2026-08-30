"""
API routes for automatic case-processing orchestration (Phase 22).
Master Specification Section 57 ("Forensic Workflow Orchestrator").

`POST /cases/{case_id}/process` is the one high-level "process this case"
operation task Phase 22 scope's own "Automatic Processing Trigger" section
asks for -- the officer never has to call a dozen separate phase APIs to
kick off automatic processing, while every one of those detailed APIs
(recovery, AI, validation, ...) remains directly callable for examiner
control, unchanged by this phase.

Requires authentication (task Phase 22 scope, "Authentication/
Authorization": findings/notifications must be attributable to the
requesting officer) -- unlike most Phase 1-20 routes, which predate Phase
21's `User`/session system entirely.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.jobs import _job_response
from app.core.case_manager import CaseManager
from app.core.processing_orchestrator import ProcessingOrchestrator
from app.core.processing_policy import ProcessingPolicy
from app.models import Job, JobStatus, User
from app.schemas.processing import (
    ProcessingPolicyRequest,
    ProcessingRunRequest,
    ProcessingRunResponse,
    ProcessingStageResponse,
)
from app.storage.db import get_db

router = APIRouter()

_STAGE_STATUS_COUNT_FIELDS = {
    JobStatus.COMPLETED.value: "stages_completed",
    JobStatus.FAILED.value: "stages_failed",
    JobStatus.SKIPPED.value: "stages_skipped",
    JobStatus.BLOCKED.value: "stages_blocked",
    JobStatus.REQUIRES_REVIEW.value: "stages_requires_review",
}


def _policy_from_request(request: ProcessingPolicyRequest | None) -> ProcessingPolicy:
    if request is None:
        return ProcessingPolicy()
    data = request.model_dump()
    if data.get("ai_analysis_types") is None:
        data.pop("ai_analysis_types")
    else:
        data["ai_analysis_types"] = tuple(data["ai_analysis_types"])
    return ProcessingPolicy(**data)


def _stage_response(job: Job) -> ProcessingStageResponse:
    return ProcessingStageResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        evidence_id=job.evidence_id,
        recording_ids=json.loads(job.recording_ids) if job.recording_ids else None,
        progress=job.progress,
        results_count=job.results_count,
        error=job.error,
        warnings=json.loads(job.warnings) if job.warnings else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


def _run_response(
    root_job: Job,
    *,
    new_finding_ids: list[int] | None = None,
    notification_ids: list[int] | None = None,
) -> ProcessingRunResponse:
    stages = [_stage_response(child) for child in sorted(root_job.child_jobs, key=lambda j: j.id)]
    counts = {field: 0 for field in _STAGE_STATUS_COUNT_FIELDS.values()}
    for stage in stages:
        field_name = _STAGE_STATUS_COUNT_FIELDS.get(stage.status)
        if field_name is not None:
            counts[field_name] += 1
    return ProcessingRunResponse(
        root_job=_job_response(root_job),
        stages=stages,
        stages_total=len(stages),
        new_finding_ids=new_finding_ids or [],
        notification_ids=notification_ids or [],
        **counts,
    )


@router.post("/cases/{case_id}/process", response_model=ProcessingRunResponse)
def process_case(
    case_id: int,
    request: ProcessingRunRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessingRunResponse:
    """Run controlled automatic processing over every evidence item in a case.

    Runs synchronously within this request (matching every prior phase's
    established pattern -- no background worker exists in this backend).
    Safe to call more than once: see `ProcessingOrchestrator.process_case`'s
    own idempotency documentation.
    """
    policy = _policy_from_request(request.policy if request else None)
    try:
        summary = ProcessingOrchestrator.process_case(
            db, case_id, policy=policy, triggered_by=current_user
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _run_response(
        summary.root_job,
        new_finding_ids=summary.new_finding_ids,
        notification_ids=summary.notification_ids,
    )


@router.get("/cases/{case_id}/processing", response_model=list[ProcessingRunResponse])
def list_processing_runs(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProcessingRunResponse]:
    """List every automatic-processing run for a case, most recent first."""
    if CaseManager.get_case(db, case_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Case with id {case_id} not found"
        )
    runs = ProcessingOrchestrator.list_processing_runs(db, case_id)
    return [_run_response(run) for run in runs]


@router.get("/processing/{root_job_id}", response_model=ProcessingRunResponse)
def get_processing_run(
    root_job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessingRunResponse:
    """Retrieve one processing run's root job and dependency-tracked stages."""
    run = ProcessingOrchestrator.get_processing_run(db, root_job_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processing run with id {root_job_id} not found",
        )
    return _run_response(run)
