"""DB-level tests for app/core/report_manager.py (Phase 18)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.provenance_manager import ProvenanceManager
from app.core.report_manager import ReportManager
from app.hashing.sha256 import sha256_bytes
from app.models import JobStatus
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base
from tests.fixtures.report_case import build_rich_case


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("EVIDENCE_ROOT", str(tmp_path / "evidence"))
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("REPORT_ROOT", str(tmp_path / "reports"))
    (tmp_path / "evidence").mkdir()
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "reports").mkdir()
    get_settings.cache_clear()

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
        get_settings.cache_clear()


def test_generate_report_creates_both_formats_by_default(db) -> None:
    rich = build_rich_case(db)
    reports = ReportManager.generate_report(db, case_id=rich.case.id)

    assert {r.report_type for r in reports} == {"json", "pdf"}
    for report in reports:
        assert report.status == "completed"
        assert report.case_id == rich.case.id
        assert report.job_id is not None
        assert report.report_hash is not None
        assert report.completed_at is not None


def test_generate_report_single_format(db) -> None:
    rich = build_rich_case(db)
    reports = ReportManager.generate_report(db, case_id=rich.case.id, formats=("json",))
    assert len(reports) == 1
    assert reports[0].report_type == "json"


def test_generate_report_hash_matches_file_content(db) -> None:
    rich = build_rich_case(db)
    reports = ReportManager.generate_report(db, case_id=rich.case.id)
    for report in reports:
        content = ReportManager.read_report_content(report)
        assert sha256_bytes(content) == report.report_hash


def test_generate_report_file_exists_under_report_root(db) -> None:
    rich = build_rich_case(db)
    reports = ReportManager.generate_report(db, case_id=rich.case.id)
    report_root = get_settings().report_root.resolve()
    for report in reports:
        path = Path(report.path)
        assert path.exists()
        assert path.is_relative_to(report_root)


def test_generate_report_json_pdf_share_one_assembled_snapshot(db) -> None:
    """Both formats are rendered from the exact same `ReportData` --
    confirm the JSON content's case name matches the case at generation
    time (no re-query drift between the two renders)."""
    rich = build_rich_case(db)
    reports = ReportManager.generate_report(db, case_id=rich.case.id)
    json_report = next(r for r in reports if r.report_type == "json")
    parsed = json.loads(ReportManager.read_report_content(json_report))
    assert parsed["case"]["case_identifier"] == rich.case.case_id
    assert parsed["metadata"]["case_id"] == rich.case.id


def test_generate_report_missing_case_raises(db) -> None:
    with pytest.raises(ValueError):
        ReportManager.generate_report(db, case_id=999999)


def test_generate_report_unsupported_format_raises(db) -> None:
    rich = build_rich_case(db)
    with pytest.raises(ValueError):
        ReportManager.generate_report(db, case_id=rich.case.id, formats=("html",))


def test_generate_report_records_provenance_event_after_content_assembled(db) -> None:
    rich = build_rich_case(db)
    history_before = ProvenanceManager.get_case_history(db, rich.case.id)
    count_before = len(history_before)

    ReportManager.generate_report(db, case_id=rich.case.id)

    history_after = ProvenanceManager.get_case_history(db, rich.case.id)
    assert len(history_after) == count_before + 1
    assert history_after[-1].operation == "report"
    assert history_after[-1].status == "completed"


def test_generate_report_on_invalid_chain_still_generates_and_reports_invalid(db) -> None:
    """Unlike Phase 17 blockchain anchoring, report generation is never
    blocked by an invalid audit chain -- it must faithfully report the
    true (invalid) state, never silently refuse or upgrade it."""
    rich = build_rich_case(db)
    from app.models import ProcessingEvent

    first_event = (
        db.query(ProcessingEvent)
        .filter(ProcessingEvent.case_id == rich.case.id)
        .order_by(ProcessingEvent.id.asc())
        .first()
    )
    first_event.status = "failed"
    db.commit()

    reports = ReportManager.generate_report(db, case_id=rich.case.id, formats=("json",))
    parsed = json.loads(ReportManager.read_report_content(reports[0]))
    assert parsed["audit"]["valid"] is False


def test_generate_report_minimal_case_succeeds(db) -> None:
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-MIN-MGR", name="Minimal"))
    reports = ReportManager.generate_report(db, case_id=case.id)
    assert len(reports) == 2
    for report in reports:
        assert report.status == "completed"


def test_list_reports_and_get_report(db) -> None:
    rich = build_rich_case(db)
    created = ReportManager.generate_report(db, case_id=rich.case.id)

    listed = ReportManager.list_reports(db, rich.case.id)
    assert [r.id for r in listed] == [r.id for r in created]

    fetched = ReportManager.get_report(db, created[0].id)
    assert fetched is not None
    assert fetched.id == created[0].id


def test_get_report_missing_returns_none(db) -> None:
    assert ReportManager.get_report(db, 999999) is None


def test_multiple_generations_are_all_retained(db) -> None:
    rich = build_rich_case(db)
    first = ReportManager.generate_report(db, case_id=rich.case.id, formats=("json",))
    second = ReportManager.generate_report(db, case_id=rich.case.id, formats=("json",))

    all_reports = ReportManager.list_reports(db, rich.case.id)
    assert len(all_reports) == 2
    assert first[0].id != second[0].id
    assert first[0].path != second[0].path


def test_generate_report_job_completed_with_correct_results_count(db) -> None:
    rich = build_rich_case(db)
    reports = ReportManager.generate_report(db, case_id=rich.case.id)
    job = reports[0].job
    assert job.status == JobStatus.COMPLETED.value
    assert job.results_count == 2
