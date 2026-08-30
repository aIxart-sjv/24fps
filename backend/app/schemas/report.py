"""
Pydantic schemas for standardized reports (Phase 18).
Master Specification Section 46 (API Design), `REPORTS` section:
`POST /api/v1/cases/{case_id}/reports`, `GET /api/v1/reports/{report_id}`,
`GET /api/v1/reports/{report_id}/download`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReportCreateRequest(BaseModel):
    """Request body for generating report(s). `formats` defaults to both
    JSON and PDF (Master Specification Section 43's two required
    outputs) when omitted."""

    formats: list[str] | None = Field(
        default=None, description="Subset of ['json', 'pdf']; both when omitted."
    )
    reason: str | None = Field(
        default=None, description="Free-text label, e.g. 'case_closure', 'periodic'."
    )


class ReportResponse(BaseModel):
    """One persisted, successfully-generated report file."""

    id: int
    case_id: int
    job_id: int | None
    report_type: str
    report_hash: str | None
    report_schema_version: str
    software_version: str | None
    status: str
    error: str | None
    warnings: list[str] | None
    created_at: datetime
    completed_at: datetime | None
