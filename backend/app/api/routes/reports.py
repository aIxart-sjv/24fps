"""
API routes for standardized reports (Phase 18).
Master Specification Section 46 (API Design), `REPORTS` section:
`POST /api/v1/cases/{case_id}/reports`, `GET /api/v1/reports/{report_id}`,
`GET /api/v1/reports/{report_id}/download`.

Only these three documented routes are implemented -- no speculative
additions (task Phase 18 scope section 25).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_case_access, require_case_access_for_report
from app.core.report_manager import ReportManager
from app.models import Case, Report
from app.schemas.report import ReportCreateRequest, ReportResponse
from app.storage.db import get_db

router = APIRouter()

_MEDIA_TYPES = {"json": "application/json", "pdf": "application/pdf"}


def _report_response(report: Report) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        case_id=report.case_id,
        job_id=report.job_id,
        report_type=report.report_type,
        report_hash=report.report_hash,
        report_schema_version=report.report_schema_version,
        software_version=report.software_version,
        status=report.status,
        error=report.error,
        warnings=json.loads(report.warnings) if report.warnings else None,
        created_at=report.created_at,
        completed_at=report.completed_at,
    )


@router.post("/cases/{case_id}/reports", response_model=list[ReportResponse])
def create_reports(
    case_id: int,
    body: ReportCreateRequest,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[ReportResponse]:
    """Generate standardized report(s) for a case (JSON and PDF by default)."""
    del case
    formats = tuple(body.formats) if body.formats is not None else None
    try:
        reports = ReportManager.generate_report(
            db, case_id=case_id, formats=formats, reason=body.reason
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [_report_response(r) for r in reports]


@router.get("/cases/{case_id}/reports", response_model=list[ReportResponse])
def list_case_reports(
    case_id: int,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[ReportResponse]:
    """List every report ever generated for a case, oldest first.

    Phase 23 gap assessment: `ReportManager.list_reports` existed with no
    HTTP route -- a report tab could create a report and read one by ID,
    but never discover previously generated ones for a case (task Phase
    23 scope, "Reporting": "Support: report creation, report status,
    report details" -- listing prior reports is implied and was missing).
    """
    del case
    return [_report_response(r) for r in ReportManager.list_reports(db, case_id)]


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report: Report = Depends(require_case_access_for_report)) -> ReportResponse:
    """Retrieve one report's metadata."""
    return _report_response(report)


@router.get("/reports/{report_id}/download")
def download_report(report: Report = Depends(require_case_access_for_report)) -> Response:
    """Download one report's file content."""
    try:
        content = ReportManager.read_report_content(report)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"report {report.id}'s file is missing on disk",
        ) from exc
    media_type = _MEDIA_TYPES.get(report.report_type, "application/octet-stream")
    filename = f"report_{report.case_id}_{report.id}.{report.report_type}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
