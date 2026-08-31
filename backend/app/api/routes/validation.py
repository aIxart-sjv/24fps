"""
API routes for the validation/ground-truth layer (Phase 14).
Master Specification Section 46 (API Design), `VALIDATION` section:
`POST /api/v1/validation/jobs`, `GET /api/v1/cases/{case_id}/validation`.

`GET /api/v1/validation/jobs/{job_id}` (also listed in Section 46) is
intentionally not duplicated here: `GET /api/v1/jobs/{job_id}` (Phase 13,
`app/api/routes/jobs.py`) already covers any `job_type`, including
`"validation"`, per that phase's own precedent for the AI job route. No
ground-truth CRUD route is added: Section 46 does not list one, and the
task explicitly says not to invent a large validation API -- ground truth
stays reachable through `ValidationManager` directly (fully usable
without HTTP), populated by controlled test scenarios/fixtures.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_case_access
from app.api.routes.jobs import _job_response
from app.core.case_authorization_service import CaseAccessDeniedError, CaseAuthorizationService
from app.core.validation_manager import ValidationManager
from app.models import Case, User, ValidationMetric
from app.schemas.validation import (
    ValidationMetricResponse,
    ValidationRunRequest,
    ValidationRunResponse,
)
from app.storage.db import get_db

router = APIRouter()


def _metric_response(metric: ValidationMetric) -> ValidationMetricResponse:
    return ValidationMetricResponse(
        id=metric.id,
        job_id=metric.job_id,
        case_id=metric.case_id,
        dataset_id=metric.dataset_id,
        validation_type=metric.validation_type,
        metric_name=metric.metric_name,
        metric_value=metric.metric_value,
        numerator=metric.numerator,
        denominator=metric.denominator,
        threshold=metric.threshold,
        notes=metric.notes,
        created_at=metric.created_at,
    )


@router.post("/validation/jobs", response_model=ValidationRunResponse)
def create_validation_job(
    request: ValidationRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ValidationRunResponse:
    """Run one validation job against a ground-truth dataset and persist the metrics.

    Runs synchronously within this request (matching Phase 13's own
    documented scoping decision -- no background/thread-pool executor
    exists anywhere in this codebase). The returned job is always in a
    terminal state (`completed`/`partial`/`failed`).

    `case_id` lives in the request body, not the URL, so this cannot use
    `require_case_access` as a sub-dependency (FastAPI would resolve its
    `case_id: int` parameter as an independent, unrelated *query*
    parameter -- there is no path segment to bind it to, and it does not
    reach into a sibling body model's fields). Authorized manually against
    `request.case_id` instead, once the body is already parsed.
    """
    try:
        CaseAuthorizationService.require_case_access(db, current_user, request.case_id)
    except CaseAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    try:
        job, metrics = ValidationManager.run_validation(
            db,
            case_id=request.case_id,
            validation_type=request.validation_type,
            dataset_id=request.dataset_id,
            iou_threshold=request.iou_threshold,
            require_class_match=request.require_class_match,
            motion_overlap_threshold=request.motion_overlap_threshold,
            correlation_time_tolerance_seconds=request.correlation_time_tolerance_seconds,
            frame_overlap_tolerance=request.frame_overlap_tolerance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ValidationRunResponse(
        job=_job_response(job), metrics=[_metric_response(m) for m in metrics]
    )


@router.get("/cases/{case_id}/validation", response_model=list[ValidationMetricResponse])
def list_case_validation_metrics(
    case_id: int,
    job_id: int | None = None,
    validation_type: str | None = None,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[ValidationMetricResponse]:
    """List persisted validation metrics for a case, optionally filtered."""
    del case
    metrics = ValidationManager.list_validation_metrics(
        db, case_id, job_id=job_id, validation_type=validation_type
    )
    return [_metric_response(m) for m in metrics]
