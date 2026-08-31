"""
API routes for AI analysis jobs (Phase 13).
Master Specification Section 46 (API Design), `AI` section:
`POST /api/v1/ai/jobs`, `GET /api/v1/cases/{case_id}/ai-results`.

`GET /api/v1/ai/jobs/{job_id}` (also listed in Section 46) is intentionally
not duplicated here: `GET /api/v1/jobs/{job_id}` (`app/api/routes/jobs.py`)
already covers any `job_type`, including `"ai"`, per this phase's own
instruction to reuse the generic job-status route rather than add a
parallel AI-specific one.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_case_access
from app.api.routes.jobs import _job_response
from app.core.ai_manager import AIManager
from app.core.case_authorization_service import CaseAccessDeniedError, CaseAuthorizationService
from app.models import AIResult, Case, User
from app.schemas.ai import AIJobCreateRequest, AIResultResponse, BoundingBoxResponse
from app.schemas.job import JobResponse
from app.storage.db import get_db

router = APIRouter()


def _result_response(result: AIResult) -> AIResultResponse:
    return AIResultResponse(
        id=result.id,
        job_id=result.job_id,
        case_id=result.case_id,
        recording_id=result.recording_id,
        analysis_type=result.analysis_type,
        model_name=result.model_name,
        model_version=result.model_version,
        frame_number=result.frame_number,
        timestamp=result.timestamp,
        class_name=result.class_name,
        confidence=result.confidence,
        bbox=BoundingBoxResponse(
            x_min=result.bbox_x_min,
            y_min=result.bbox_y_min,
            x_max=result.bbox_x_max,
            y_max=result.bbox_y_max,
        ),
        track_id=result.track_id,
        source_artifact=result.source_artifact,
        created_at=result.created_at,
    )


@router.post("/ai/jobs", response_model=JobResponse)
def create_ai_job(
    request: AIJobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Run one AI analysis job over the given recordings and persist the results.

    Runs synchronously within this request (task Phase 13 scope's own
    documented scoping decision, matching every prior phase's pattern --
    no background/thread-pool executor exists anywhere in this codebase).
    The returned job is always in a terminal state (`completed`/`partial`/
    `failed`) -- this endpoint never returns while a job is still
    `pending`/`running`.

    `case_id` lives in the request body, not the URL -- see
    `app/api/routes/validation.py`'s `create_validation_job` for why that
    means authorizing manually here rather than via a `require_case_access`
    sub-dependency (which would bind `case_id` as an unrelated query
    parameter instead).
    """
    try:
        CaseAuthorizationService.require_case_access(db, current_user, request.case_id)
    except CaseAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    try:
        job = AIManager.run_job(
            db,
            case_id=request.case_id,
            recording_ids=request.recording_ids,
            analysis_types=request.analysis_types,
            sampling_strategy=request.sampling_strategy,
            sampling_value=request.sampling_value,
            confidence_threshold=request.confidence_threshold,
            face_confidence_threshold=request.face_confidence_threshold,
            classes=request.classes,
            tracker=request.tracker,
            prefer_gpu=request.prefer_gpu,
            frame_redundancy_enabled=request.frame_redundancy_enabled,
            frame_redundancy_threshold=request.frame_redundancy_threshold,
            frame_redundancy_max_skip_run=request.frame_redundancy_max_skip_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _job_response(job)


@router.get("/cases/{case_id}/ai-results", response_model=list[AIResultResponse])
def list_ai_results(
    case_id: int,
    recording_id: int | None = None,
    analysis_type: str | None = None,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[AIResultResponse]:
    """List persisted AI results (object/face detections) for a case."""
    del case
    results = AIManager.list_ai_results(
        db, case_id, recording_id=recording_id, analysis_type=analysis_type
    )
    return [_result_response(r) for r in results]
