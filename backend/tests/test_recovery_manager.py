"""Tests for app/core/recovery_manager.py (Phase 10), against small synthetic
CP Plus fixtures — fast, no real evidence or FFmpeg required. The real-
evidence acceptance test lives in
tests/test_cp_plus_recovery_real_evidence_integration.py.
"""

from __future__ import annotations

import hashlib
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
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.core.recovery_manager import RecoveryManager
from app.models import Artifact, Case, Evidence
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


def _no_video_segment_bytes() -> bytes:
    return _outer_header_bytes(1, 2) + _record_bytes(0xF1, 1, b'{"telemetry": true}')


@pytest.fixture
def db_session_and_engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Matches tests/test_recording_manager.py's own fixture exactly."""
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


def _make_case(db: Session, case_id: str = "CASE-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Test case"))


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


def test_run_recovery_on_clean_segment_reports_recovered_and_registers_artifact(
    db_session_and_engine,
):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _clean_segment_bytes()
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    result = RecoveryManager.run_recovery(db, recording.id)

    assert result.status == "recovered"
    assert result.method == "vendor_damaged_recovery"
    assert result.frames_recovered == 3
    assert result.frame_continuity == 1.0
    assert result.artifact_id is not None

    artifact = db.query(Artifact).filter(Artifact.id == result.artifact_id).first()
    assert artifact is not None
    assert Path(artifact.path).is_file()
    assert artifact.sha256 == hashlib.sha256(Path(artifact.path).read_bytes()).hexdigest()

    db.refresh(recording)
    assert recording.recovery_status == "recovered"
    assert recording.recovery_method == "vendor_damaged_recovery"


def test_run_recovery_on_truncated_segment_reports_partial(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _truncated_segment_bytes()
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    result = RecoveryManager.run_recovery(db, recording.id)

    assert result.status == "partial"
    assert result.artifact_id is not None
    assert result.notes is not None and "truncated" in result.notes


def test_run_recovery_with_no_video_reports_no_recovery_found_and_registers_no_artifact(
    db_session_and_engine,
):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _no_video_segment_bytes()
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    result = RecoveryManager.run_recovery(db, recording.id)

    assert result.status == "no_recovery_found"
    assert result.artifact_id is None


def test_run_recovery_raises_for_missing_recording(db_session_and_engine):
    db, _evidence_root = db_session_and_engine
    with pytest.raises(ValueError, match="not found"):
        RecoveryManager.run_recovery(db, 999)


def test_recovery_result_traces_back_to_evidence_and_recording(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _clean_segment_bytes()
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    result = RecoveryManager.run_recovery(db, recording.id)

    assert result.evidence_id == evidence.id
    assert result.recording_id == recording.id
    assert result.evidence.id == evidence.id
    assert result.recording.id == recording.id


def test_run_recovery_does_not_modify_source_evidence_file(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _truncated_segment_bytes()
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]
    source_path = Path(evidence.source_path)
    before_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    RecoveryManager.run_recovery(db, recording.id)

    after_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert before_hash == after_hash


def test_list_recovery_results_returns_every_attempt_for_the_evidence(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _clean_segment_bytes()
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    RecoveryManager.run_recovery(db, recording.id)
    RecoveryManager.run_recovery(db, recording.id)

    results = RecoveryManager.list_recovery_results(db, evidence.id)
    assert len(results) == 2
    assert all(r.evidence_id == evidence.id for r in results)


def test_run_recovery_never_writes_into_evidence_root(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _clean_segment_bytes()
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    before_files = set(evidence_root.rglob("*"))
    RecoveryManager.run_recovery(db, recording.id)
    after_files = set(evidence_root.rglob("*"))

    assert before_files == after_files
