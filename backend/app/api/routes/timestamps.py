"""
API route for timestamp normalization (Phase 11).
Master Specification Section 46 (API Design), `TIMELINE` section:
`POST /api/v1/timestamps/normalize` — the only Section 46 timeline route
this phase implements (`timeline/build`/`GET timeline` are Phase 12's
canonical-timeline territory).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.timestamp_manager import TimestampManager
from app.schemas.timestamp import TimestampNormalizeRequest, TimestampNormalizeResponse
from app.storage.db import get_db
from app.timeline import NormalizationMethod, ReferencePair

router = APIRouter()


@router.post("/timestamps/normalize", response_model=TimestampNormalizeResponse)
def normalize_timestamp(
    request: TimestampNormalizeRequest, db: Session = Depends(get_db)
) -> TimestampNormalizeResponse:
    """Normalize one recording's original timestamps and persist the result.

    Never fails the HTTP request for an `UNKNOWN`/`UNVERIFIED`/`PARTIAL`
    outcome — those are legitimate, honestly-reported results, not
    errors. Only a missing recording or an invalid reference method
    fails the request.
    """
    reference: ReferencePair | None = None
    if request.reference is not None:
        try:
            method = NormalizationMethod(request.reference.method)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unrecognized normalization method {request.reference.method!r}",
            ) from exc
        reference = ReferencePair(
            reference_timestamp=request.reference.reference_timestamp,
            reference_timezone=request.reference.reference_timezone,
            reference_source=request.reference.reference_source,
            reference_basis=request.reference.reference_basis,
            method=method,
        )

    try:
        outcome = TimestampManager.normalize_recording(
            db,
            request.recording_id,
            source_timezone=request.source_timezone,
            source_timezone_basis=request.source_timezone_basis,
            reference=reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return TimestampNormalizeResponse(
        recording_id=outcome.recording.id,
        overall_status=outcome.overall_status.value,
        source=outcome.start_result.source.value,
        start_original=outcome.recording.start_original,
        end_original=outcome.recording.end_original,
        start_normalized=outcome.recording.start_normalized,
        end_normalized=outcome.recording.end_normalized,
        start_status=outcome.start_result.status.value,
        end_status=outcome.end_result.status.value,
        start_reason=outcome.start_result.reason,
        end_reason=outcome.end_result.reason,
        source_timezone=outcome.start_result.source_timezone,
        source_timezone_basis=outcome.start_result.source_timezone_basis,
        offset_seconds=outcome.start_result.offset_seconds,
        method=outcome.start_result.method.value,
    )
