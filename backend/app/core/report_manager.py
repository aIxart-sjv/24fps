"""
Business logic for standardized report generation (Phase 18).
Master Specification Section 43 ("Reporting Engine").

This is the DB-aware orchestration layer built on `app.reporting.*` (pure
content assembly/rendering) and the existing `JobManager` (task Phase 18
scope section 23: "If the existing job system is appropriate, reuse it" --
this module never builds a second job-tracking mechanism). One
`generate_report` call:

    1. verify the case exists
    2. create + start a `Job` (`REPORT_JOB_TYPE`)
    3. assemble `ReportData` ONCE (read-only) -- every requested format
       renders from this same snapshot, so JSON and PDF content are
       guaranteed consistent with each other even though they become two
       separate `Report` rows
    4. render + hash + write each requested format under REPORT_ROOT
       (never inside EVIDENCE_ROOT/ARTIFACT_ROOT -- reuses
       `app.storage.artifact_store.resolve_report_path`/
       `prepare_report_directory`, never a second file-storage system)
    5. persist one `Report` row per successfully-written format
    6. finish the `Job`
    7. record the report-generation operation itself as a `ProcessingEvent`
       (task Phase 18 scope section 15/23) -- strictly *after* step 3, so
       the report's own audit/provenance section (already assembled) never
       includes the event describing its own creation. Mirrors Phase 17's
       identical anchor-then-record-event ordering, and for the identical
       reason: it is a later, independent extension of the chain, never a
       retroactive change to what the report already captured.

If report generation fails partway (a render or write error), no partial
`Report` row is ever persisted for the failed format -- the failure is
recorded on the `Job` instead (task Phase 18 scope section 24: "Do not
report success if required report generation failed").
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.audit import ActorType, ProcessingOperation
from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.job_manager import JobManager
from app.core.provenance_manager import ProvenanceManager
from app.hashing.sha256 import sha256_bytes
from app.models import REPORT_JOB_TYPE, Case, Job, JobStatus, Report
from app.reporting.evidence_report import ReportData, assemble_report_data
from app.reporting.json_report import render_json
from app.reporting.pdf_report import render_pdf
from app.storage.artifact_store import prepare_report_directory

__all__ = ["DEFAULT_REPORT_FORMATS", "SUPPORTED_REPORT_FORMATS", "ReportManager"]

#: The two formats Master Specification Section 43 requires ("produces:
#: 1. standardized JSON, 2. human-readable PDF"). Optional formats
#: (HTML/CSV) Section 43 also lists are not implemented in this phase.
SUPPORTED_REPORT_FORMATS = ("json", "pdf")
DEFAULT_REPORT_FORMATS = ("json", "pdf")

_RENDERERS = {"json": render_json, "pdf": render_pdf}


class ReportManager:
    """Service layer for generating and retrieving standardized reports."""

    @staticmethod
    def generate_report(
        db: Session,
        *,
        case_id: int,
        formats: tuple[str, ...] | None = None,
        reason: str | None = None,
    ) -> list[Report]:
        """Generate one or more standardized report files for a case.

        Args:
            db: Database session.
            case_id: The case to report on. Must exist.
            formats: Which formats to generate (`"json"`/`"pdf"`).
                Defaults to `DEFAULT_REPORT_FORMATS` (both) when omitted.
            reason: Optional free-text note recorded on the underlying
                `Job` and provenance event (e.g. `"case_closure"`).

        Returns:
            The persisted `Report` rows, one per successfully-generated
            format, in the order requested.

        Raises:
            ValueError: If `case_id` does not exist or `formats` contains
                an unsupported value.
        """
        case = CaseManager.get_case(db, case_id)
        if case is None:
            raise ValueError(f"Case with id {case_id} not found")

        requested = formats if formats is not None else DEFAULT_REPORT_FORMATS
        unsupported = [f for f in requested if f not in SUPPORTED_REPORT_FORMATS]
        if unsupported:
            raise ValueError(
                f"unsupported report format(s) {unsupported!r}; "
                f"supported formats are {SUPPORTED_REPORT_FORMATS!r}"
            )

        settings = get_settings()
        job = JobManager.create_job(
            db,
            case_id=case_id,
            job_type=REPORT_JOB_TYPE,
            parameters={"formats": list(requested), "reason": reason},
        )
        job = JobManager.mark_running(db, job)

        try:
            data = assemble_report_data(db, case, software_version=settings.app_version)
        except Exception as exc:  # noqa: BLE001 - always recorded, then re-raised
            JobManager.finish_job(
                db, job, status=JobStatus.FAILED, error=f"report assembly failed: {exc}"
            )
            raise

        reports: list[Report] = []
        warnings: list[str] = []
        try:
            for report_format in requested:
                report = ReportManager._render_and_persist(
                    db, case=case, job=job, report_format=report_format, data=data
                )
                reports.append(report)
        except Exception as exc:  # noqa: BLE001 - always recorded, then re-raised
            JobManager.finish_job(
                db,
                job,
                status=JobStatus.FAILED,
                results_count=len(reports),
                error=f"report rendering failed: {exc}",
            )
            raise

        if data.limitations:
            warnings.append(f"{len(data.limitations)} limitation(s) recorded in report content")

        JobManager.finish_job(
            db,
            job,
            status=JobStatus.COMPLETED,
            results_count=len(reports),
            warnings=warnings or None,
        )

        ProvenanceManager.record_event(
            db,
            case_id=case_id,
            job_id=job.id,
            operation=ProcessingOperation.REPORT.value,
            actor="ReportManager",
            actor_type=ActorType.SYSTEM,
            tool="app.reporting",
            tool_version=data.metadata.report_schema_version,
            software_version=settings.app_version,
            status=JobStatus.COMPLETED,
            parameters={"formats": list(requested), "reason": reason},
            description=f"generated standardized report(s) for case {case_id}",
        )

        return reports

    @staticmethod
    def _render_and_persist(
        db: Session, *, case: Case, job: Job, report_format: str, data: ReportData
    ) -> Report:
        content = _RENDERERS[report_format](data)
        content_hash = sha256_bytes(content)

        relative_path = f"{case.id}/report_{job.id}.{report_format}"
        absolute_path = prepare_report_directory(relative_path)
        absolute_path.write_bytes(content)

        completed_at = datetime.now(UTC)
        report = Report(
            case_id=case.id,
            job_id=job.id,
            report_type=report_format,
            path=str(absolute_path),
            report_hash=content_hash,
            report_schema_version=data.metadata.report_schema_version,
            software_version=data.metadata.software_version,
            status="completed",
            error=None,
            warnings=None,
            completed_at=completed_at,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    # ---- Listing / lookup ---------------------------------------------

    @staticmethod
    def list_reports(db: Session, case_id: int) -> list[Report]:
        """List every report ever generated for a case, oldest first."""
        return db.query(Report).filter(Report.case_id == case_id).order_by(Report.id.asc()).all()

    @staticmethod
    def get_report(db: Session, report_id: int) -> Report | None:
        """Retrieve one report by primary key."""
        return db.query(Report).filter(Report.id == report_id).first()

    @staticmethod
    def read_report_content(report: Report) -> bytes:
        """Read a persisted report's file content from disk.

        Args:
            report: The report row whose file to read.

        Returns:
            The exact bytes written at generation time.

        Raises:
            FileNotFoundError: If the underlying file is missing.
        """
        return Path(report.path).read_bytes()
