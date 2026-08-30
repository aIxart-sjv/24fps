"""Tests for app/core/job_manager.py (Phase 13) -- the generic job
persistence/lifecycle layer, independent of AI-specific behavior."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.case_manager import CaseManager
from app.core.job_manager import JobManager
from app.models import Case, JobStatus
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _make_case(db, case_id: str = "CASE-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Test case"))


def test_create_job_defaults_to_pending(db) -> None:
    case = _make_case(db)

    job = JobManager.create_job(db, case_id=case.id, job_type="ai")

    assert job.status == JobStatus.PENDING.value
    assert job.case_id == case.id
    assert job.job_type == "ai"
    assert job.results_count == 0
    assert job.started_at is None
    assert job.completed_at is None


def test_create_job_records_reproducibility_metadata(db) -> None:
    case = _make_case(db)

    job = JobManager.create_job(
        db,
        case_id=case.id,
        job_type="ai",
        recording_ids=[1, 2],
        analysis_types=["object_detection", "motion_detection"],
        parameters={"confidence_threshold": 0.25, "sampling_strategy": "fps"},
    )

    import json

    assert json.loads(job.recording_ids) == [1, 2]
    assert json.loads(job.analysis_types) == ["object_detection", "motion_detection"]
    assert json.loads(job.parameters) == {
        "confidence_threshold": 0.25,
        "sampling_strategy": "fps",
    }
    assert job.software_version is not None


def test_mark_running_sets_started_at_and_status(db) -> None:
    case = _make_case(db)
    job = JobManager.create_job(db, case_id=case.id, job_type="ai")

    running = JobManager.mark_running(db, job)

    assert running.status == JobStatus.RUNNING.value
    assert running.started_at is not None


def test_finish_job_completed_sets_progress_to_one(db) -> None:
    case = _make_case(db)
    job = JobManager.mark_running(db, JobManager.create_job(db, case_id=case.id, job_type="ai"))

    finished = JobManager.finish_job(
        db, job, status=JobStatus.COMPLETED, worker="cpu", results_count=5
    )

    assert finished.status == JobStatus.COMPLETED.value
    assert finished.progress == 1.0
    assert finished.worker == "cpu"
    assert finished.results_count == 5
    assert finished.completed_at is not None


def test_finish_job_partial_records_warnings(db) -> None:
    case = _make_case(db)
    job = JobManager.mark_running(db, JobManager.create_job(db, case_id=case.id, job_type="ai"))

    finished = JobManager.finish_job(
        db,
        job,
        status=JobStatus.PARTIAL,
        results_count=2,
        warnings=["recording 99: not found"],
    )

    import json

    assert finished.status == JobStatus.PARTIAL.value
    assert json.loads(finished.warnings) == ["recording 99: not found"]
    # PARTIAL never silently claims full completion via progress=1.0
    # unless explicitly given.
    assert finished.progress is None


def test_finish_job_failed_records_error(db) -> None:
    case = _make_case(db)
    job = JobManager.mark_running(db, JobManager.create_job(db, case_id=case.id, job_type="ai"))

    finished = JobManager.finish_job(
        db, job, status=JobStatus.FAILED, error="no recordings could be processed"
    )

    assert finished.status == JobStatus.FAILED.value
    assert finished.error == "no recordings could be processed"


def test_finish_job_records_model_versions(db) -> None:
    case = _make_case(db)
    job = JobManager.mark_running(db, JobManager.create_job(db, case_id=case.id, job_type="ai"))

    finished = JobManager.finish_job(
        db,
        job,
        status=JobStatus.COMPLETED,
        model_versions={"yolov8n.pt": "yolov8n"},
        results_count=1,
    )

    import json

    assert json.loads(finished.model_versions) == {"yolov8n.pt": "yolov8n"}


def test_update_progress(db) -> None:
    case = _make_case(db)
    job = JobManager.mark_running(db, JobManager.create_job(db, case_id=case.id, job_type="ai"))

    updated = JobManager.update_progress(db, job, 0.5)

    assert updated.progress == 0.5


def test_get_job_returns_none_for_missing(db) -> None:
    assert JobManager.get_job(db, 999999) is None


def test_get_job_returns_the_created_job(db) -> None:
    case = _make_case(db)
    job = JobManager.create_job(db, case_id=case.id, job_type="ai")

    fetched = JobManager.get_job(db, job.id)

    assert fetched is not None
    assert fetched.id == job.id
