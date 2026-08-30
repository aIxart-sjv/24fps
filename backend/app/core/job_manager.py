"""
Generic processing-job persistence and lifecycle (Phase 13).
Master Specification Section 48 ("Job System").

No job system existed anywhere in this codebase before Phase 13 (see
`app/models/job.py`'s module docstring). This module is the generic
CRUD/lifecycle layer only -- it knows nothing about what any particular
`job_type` actually does. `app.core.ai_manager.AIManager` is the AI
business-logic layer built on top of it; a future phase's manager
(validation, reporting, ...) can reuse this same module rather than
building a parallel job persistence layer.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Job, JobStatus

__all__ = ["JobManager"]


class JobManager:
    """Service layer for generic job creation and lifecycle transitions."""

    @staticmethod
    def create_job(
        db: Session,
        *,
        case_id: int,
        job_type: str,
        evidence_id: int | None = None,
        recording_ids: list[int] | None = None,
        analysis_types: list[str] | None = None,
        parameters: dict[str, object] | None = None,
    ) -> Job:
        """Create a new job in `PENDING` state.

        Args:
            db: Database session.
            case_id: Primary key of the owning case.
            job_type: Free-text job type (this phase always writes
                `app.models.job.AI_JOB_TYPE`; other job types are a
                future phase's concern, not constrained here).
            evidence_id: Primary key of a related evidence item, if any.
            recording_ids: Recordings this job will process, if
                applicable to `job_type`.
            analysis_types: Requested analysis types, if applicable.
            parameters: Arbitrary job configuration (sampling strategy,
                thresholds, ...) -- always recorded for reproducibility,
                never silently applied without being persisted.

        Returns:
            The created `Job`, with `software_version` stamped from the
            running backend build.
        """
        job = Job(
            case_id=case_id,
            evidence_id=evidence_id,
            job_type=job_type,
            status=JobStatus.PENDING.value,
            recording_ids=json.dumps(recording_ids) if recording_ids is not None else None,
            analysis_types=json.dumps(analysis_types) if analysis_types is not None else None,
            parameters=json.dumps(parameters) if parameters is not None else None,
            software_version=get_settings().app_version,
            results_count=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_running(db: Session, job: Job) -> Job:
        """Transition a job to `RUNNING`, stamping `started_at`."""
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def finish_job(
        db: Session,
        job: Job,
        *,
        status: JobStatus,
        worker: str | None = None,
        model_versions: dict[str, str] | None = None,
        results_count: int | None = None,
        progress: float | None = None,
        output_artifacts: list[int] | None = None,
        error: str | None = None,
        warnings: list[str] | None = None,
    ) -> Job:
        """Transition a job to a terminal state, stamping `completed_at`.

        Args:
            db: Database session.
            job: The job to finish.
            status: Must be `COMPLETED`, `PARTIAL`, or `FAILED` -- never
                report `COMPLETED` for work that was only partially done
                (task Phase 13 scope: "Do not report COMPLETED when
                requested analysis was only partially processed.").
            worker: The actual processing device used, if applicable.
            model_versions: `{model_name: model_version}` for every model
                actually used -- reproducibility (task: "Do not use
                floating/latest model versions without recording the
                actual version used.").
            results_count: Total output records produced.
            progress: Final progress value. Defaults to `1.0` for
                `COMPLETED`, left unchanged otherwise.
            output_artifacts: IDs of any derived artifacts produced.
            error: A summary error message, if the job did not fully
                succeed.
            warnings: Non-fatal issues encountered.

        Returns:
            The updated `Job`.
        """
        job.status = status.value
        job.completed_at = datetime.now(UTC)
        if worker is not None:
            job.worker = worker
        if model_versions is not None:
            job.model_versions = json.dumps(model_versions)
        if results_count is not None:
            job.results_count = results_count
        if progress is not None:
            job.progress = progress
        elif status == JobStatus.COMPLETED:
            job.progress = 1.0
        if output_artifacts is not None:
            job.output_artifacts = json.dumps(output_artifacts)
        if error is not None:
            job.error = error
        if warnings is not None:
            job.warnings = json.dumps(warnings)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def update_progress(db: Session, job: Job, progress: float) -> Job:
        """Update a running job's progress fraction (`0.0`-`1.0`)."""
        job.progress = progress
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_job(db: Session, job_id: int) -> Job | None:
        """Fetch one job by primary key, or `None` if it does not exist."""
        return db.query(Job).filter(Job.id == job_id).first()
