"""Tests for app/core/processing_orchestrator.py (Phase 22), against small
synthetic CP Plus fixtures -- fast, no real evidence or FFmpeg required.
Mirrors tests/test_recovery_manager.py's own fixture pattern exactly. The
real-evidence acceptance test lives in
tests/test_cp_plus_processing_orchestrator_real_evidence_integration.py.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.cp_plus.models import (
    ADIT_MAGIC,
    OUTER_HEADER_SIZE,
    RECORD_FOOTER_MAGIC,
    RECORD_HEADER_SIZE,
    RECORD_MAGIC,
)
from app.config import get_settings
from app.core.auth_manager import AuthManager
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.processing_orchestrator import ProcessingOrchestrator
from app.core.processing_policy import ProcessingPolicy
from app.models import (
    Case,
    CaseStatus,
    Evidence,
    Finding,
    FindingType,
    JobStatus,
    Notification,
    RecoveryResult,
)
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base

_ANNEXB_PREFIX = b"\x00" * 33


def _outer_header_bytes(start_counter: int, end_counter: int) -> bytes:
    return (
        ADIT_MAGIC
        + struct.pack("<II", start_counter, end_counter)
        + b"\x00" * (OUTER_HEADER_SIZE - 16)
    )


def _record_bytes(type_tag: int, counter: int, body: bytes) -> bytes:
    length = RECORD_HEADER_SIZE + len(body) + 8
    header = RECORD_MAGIC + struct.pack("<III", type_tag, counter, length)
    footer = RECORD_FOOTER_MAGIC + struct.pack("<I", length)
    return header + body + footer


def _nal(nal_unit_type: int) -> bytes:
    first_byte = (nal_unit_type << 1) & 0xFF
    return b"\x00\x00\x01" + bytes([first_byte, 0x01]) + b"\xff\xee"


def _keyframe_marker_body() -> bytes:
    return _ANNEXB_PREFIX + _nal(32) + _nal(33) + _nal(34) + _nal(19)


def _video_frame_body() -> bytes:
    return _ANNEXB_PREFIX + _nal(1)


def _clean_segment_bytes(start_counter: int = 100) -> bytes:
    return (
        _outer_header_bytes(start_counter, start_counter + 3)
        + _record_bytes(0xFD, start_counter, _keyframe_marker_body())
        + _record_bytes(0xFC, start_counter + 1, _video_frame_body())
        + _record_bytes(0xFC, start_counter + 2, _video_frame_body())
    )


def _truncated_segment_bytes(start_counter: int = 100) -> bytes:
    good = _record_bytes(0xFD, start_counter, _keyframe_marker_body()) + _record_bytes(
        0xFC, start_counter + 1, _video_frame_body()
    )
    bad_header = RECORD_MAGIC + struct.pack("<III", 0xFC, start_counter + 2, 999_999)
    return _outer_header_bytes(start_counter, start_counter + 3) + good + bad_header


@pytest.fixture
def db_session_and_engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Matches tests/test_recovery_manager.py's own fixture exactly."""
    evidence_root = tmp_path / "evidence"
    artifact_root = tmp_path / "artifacts"
    evidence_root.mkdir()
    artifact_root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    try:
        yield db, evidence_root
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        get_settings.cache_clear()


def _make_case(db: Session, case_id: str = "CASE-ORCH-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Orchestrator test"))


def _register_evidence(
    db: Session, case: Case, evidence_root: Path, filename: str, content: bytes
) -> Evidence:
    path = evidence_root / filename
    path.write_bytes(content)
    return EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=Path(filename).stem, source_type="native_export", source_path=str(path)
        ),
    )


#: Never runs AI/correlation/validation -- keeps these synthetic-fixture
#: tests fast and focused on orchestration/idempotency/findings behavior,
#: not on the AI model stack (already covered by tests/test_ai_manager.py).
_NO_AI_POLICY = ProcessingPolicy(run_ai=False)


def test_process_case_clean_cp_plus_evidence_completes(db_session_and_engine) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _clean_segment_bytes(),
    )

    summary = ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)

    # Overall status is PARTIAL, not FAILED or COMPLETED: every evidence-
    # level stage succeeds cleanly, but case-level validation has no
    # ground-truth dataset configured and is honestly REQUIRES_REVIEW --
    # that alone must not be silently rounded up to COMPLETED.
    assert summary.root_job.status == JobStatus.PARTIAL.value
    assert summary.root_job.job_type == "orchestration"
    db.refresh(case)
    assert case.status == CaseStatus.REVIEW

    stages_by_type = {child.job_type: child.status for child in summary.root_job.child_jobs}
    for stage in ("integrity", "identification", "enumeration", "recovery", "timestamp_normalization", "timeline"):
        assert stages_by_type[stage] == JobStatus.COMPLETED.value, stage
    # `extraction` may itself be PARTIAL here: this fixture's fake NAL
    # payloads are not real decodable video, so ffmpeg's mux-to-MP4 step
    # legitimately fails on it (a property of the synthetic fixture, not
    # of the orchestrator) -- it must never be FAILED/SKIPPED/BLOCKED.
    assert stages_by_type["extraction"] in (JobStatus.COMPLETED.value, JobStatus.PARTIAL.value)
    assert stages_by_type["validation"] == JobStatus.REQUIRES_REVIEW.value
    assert all(child.parent_job_id == summary.root_job.id for child in summary.root_job.child_jobs)


def test_process_case_unsupported_evidence_produces_unsupported_format_finding(
    db_session_and_engine,
) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db, case, evidence_root, "garbage.cpv", b"not a real cpv file at all, no magic header"
    )

    summary = ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)

    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    assert any(f.finding_type == FindingType.UNSUPPORTED_FORMAT.value for f in findings)
    assert summary.root_job.status in (JobStatus.PARTIAL.value, JobStatus.SKIPPED.value)


def test_process_case_truncated_segment_produces_recovery_and_corruption_findings(
    db_session_and_engine,
) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _truncated_segment_bytes(),
    )

    ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)

    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    finding_types = {f.finding_type for f in findings}
    assert FindingType.PARTIAL_RECOVERY.value in finding_types
    # Every finding's forensic language stays hedged -- never a stronger
    # claim ("tampering", "guilt") than the underlying signal supports.
    for finding in findings:
        lowered = finding.description.lower()
        assert "tamper" not in lowered
        assert "guilt" not in lowered


def test_process_case_is_idempotent_on_rerun(db_session_and_engine) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _truncated_segment_bytes(),
    )

    ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)
    first_finding_count = db.query(Finding).count()
    first_recovery_count = db.query(RecoveryResult).count()

    ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)
    second_finding_count = db.query(Finding).count()
    second_recovery_count = db.query(RecoveryResult).count()

    # No new recovery attempt and no duplicate finding rows on a second,
    # non-forced run -- the existing open finding is merged into instead.
    assert second_recovery_count == first_recovery_count
    assert second_finding_count == first_finding_count

    merged = (
        db.query(Finding)
        .filter(Finding.case_id == case.id, Finding.finding_type == FindingType.PARTIAL_RECOVERY.value)
        .one()
    )
    assert merged.occurrence_count >= 1


def test_process_case_force_reprocess_creates_new_recovery_attempt(db_session_and_engine) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _truncated_segment_bytes(),
    )
    force_policy = ProcessingPolicy(run_ai=False, force_reprocess=True)

    ProcessingOrchestrator.process_case(db, case.id, policy=force_policy)
    first_recovery_count = db.query(RecoveryResult).count()

    ProcessingOrchestrator.process_case(db, case.id, policy=force_policy)
    second_recovery_count = db.query(RecoveryResult).count()

    assert second_recovery_count == first_recovery_count * 2


def test_process_case_recovery_disabled_creates_review_finding(db_session_and_engine) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _clean_segment_bytes(),
    )
    policy = ProcessingPolicy(run_ai=False, run_recovery=False)

    ProcessingOrchestrator.process_case(db, case.id, policy=policy)

    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    assert any(f.finding_type == FindingType.RECOVERY_AVAILABLE_FOR_REVIEW.value for f in findings)
    assert db.query(RecoveryResult).count() == 0


def test_process_case_validation_not_run_without_ground_truth(db_session_and_engine) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _clean_segment_bytes(),
    )

    ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)

    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    assert any(f.finding_type == FindingType.VALIDATION_NOT_RUN.value for f in findings)


def test_process_case_missing_case_raises(db_session_and_engine) -> None:
    db, _evidence_root = db_session_and_engine
    with pytest.raises(ValueError, match="not found"):
        ProcessingOrchestrator.process_case(db, 999)


def test_process_case_notifies_triggering_officer(db_session_and_engine) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _truncated_segment_bytes(),
    )
    officer = AuthManager.create_user(
        db, username="officer1", display_name="Officer One", password="password123"
    )

    summary = ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY, triggered_by=officer)

    assert summary.notification_ids
    notifications = db.query(Notification).filter(Notification.recipient_user_id == officer.id).all()
    assert len(notifications) == len(summary.new_finding_ids)
    assert {n.finding_id for n in notifications} == set(summary.new_finding_ids)


def test_process_case_without_triggering_user_creates_no_notifications(
    db_session_and_engine,
) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _truncated_segment_bytes(),
    )

    summary = ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)

    assert summary.new_finding_ids  # findings still generated
    assert summary.notification_ids == []
    assert db.query(Notification).count() == 0


def test_get_processing_run_returns_stages(db_session_and_engine) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _clean_segment_bytes(),
    )

    summary = ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)
    fetched = ProcessingOrchestrator.get_processing_run(db, summary.root_job.id)

    assert fetched is not None
    assert fetched.id == summary.root_job.id
    assert len(fetched.child_jobs) > 0


def test_list_processing_runs_orders_most_recent_first(db_session_and_engine) -> None:
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _clean_segment_bytes(),
    )

    first = ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)
    second = ProcessingOrchestrator.process_case(db, case.id, policy=_NO_AI_POLICY)

    runs = ProcessingOrchestrator.list_processing_runs(db, case.id)
    assert [r.id for r in runs] == [second.root_job.id, first.root_job.id]
