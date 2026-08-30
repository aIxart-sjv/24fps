"""Tests for app/core/recording_manager.py (Phase 9), against small
synthetic CP Plus fixtures — fast, no real evidence or FFmpeg required for
the DB-orchestration logic itself. The full successful-extraction path
(real FFmpeg mux/transcode) is covered by
tests/test_cp_plus_extraction_real_evidence_integration.py against the
real evidence package.
"""

from __future__ import annotations

import json
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
from app.models import Case, Evidence, Recording, RecordingMetadata
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


def _synthetic_cpv_bytes(*, start_counter: int, end_counter: int, with_video: bool) -> bytes:
    content = _outer_header_bytes(start_counter, end_counter)
    if with_video:
        content += _record_bytes(0xFD, start_counter, _keyframe_marker_body())
    else:
        content += _record_bytes(0xF1, start_counter, b'{"telemetry": true}')
    return content


@pytest.fixture
def db_session_and_engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """An isolated DB + EVIDENCE_ROOT/ARTIFACT_ROOT, matching the established
    monkeypatch + get_settings.cache_clear() root-override pattern from
    tests/test_artifact_storage.py.
    """
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


# --- enumerate_recordings ---


def test_enumerate_recordings_persists_recording_and_baseline_metadata(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _synthetic_cpv_bytes(start_counter=100, end_counter=200, with_video=True)
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )

    recordings = RecordingManager.enumerate_recordings(db, evidence.id)

    assert len(recordings) == 1
    recording = recordings[0]
    assert recording.channel == 1
    assert recording.recording_id == "NVR_ch1_main_20260101120000_20260101120010"

    metadata = {
        m.key: m.value
        for m in db.query(RecordingMetadata)
        .filter(RecordingMetadata.recording_id == recording.id)
        .all()
    }
    assert metadata["vendor"] == "CP Plus"
    assert metadata["timestamp_status"] == "raw_counter_unvalidated"
    assert metadata["raw_timestamp"] == "100"


def test_enumerate_recordings_is_idempotent(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _synthetic_cpv_bytes(start_counter=1, end_counter=2, with_video=True)
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )

    first = RecordingManager.enumerate_recordings(db, evidence.id)
    second = RecordingManager.enumerate_recordings(db, evidence.id)

    assert first[0].id == second[0].id
    assert db.query(Recording).count() == 1


def test_enumerate_recordings_returns_empty_for_non_cp_plus_evidence(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    evidence = _register_evidence(db, case, evidence_root, "random.bin", b"not a cpv file")

    recordings = RecordingManager.enumerate_recordings(db, evidence.id)

    assert recordings == []
    assert db.query(Recording).count() == 0


def test_enumerate_recordings_raises_for_missing_evidence(db_session_and_engine):
    db, _evidence_root = db_session_and_engine
    with pytest.raises(ValueError, match="not found"):
        RecordingManager.enumerate_recordings(db, 999)


# --- link_session ---


def test_link_session_requires_at_least_two_segments(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _synthetic_cpv_bytes(start_counter=1, end_counter=2, with_video=True)
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )
    with pytest.raises(ValueError, match="at least 2"):
        RecordingManager.link_session(db, [evidence.id])


def test_link_session_creates_session_recording_spanning_segments(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    seg1 = _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _synthetic_cpv_bytes(start_counter=100, end_counter=200, with_video=True),
    )
    seg2 = _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120010_20260101120020.cpv",
        _synthetic_cpv_bytes(start_counter=200, end_counter=300, with_video=True),
    )

    session_recording = RecordingManager.link_session(db, [seg1.id, seg2.id])

    assert session_recording.recording_id.startswith("SESSION-CASE-1-")
    assert session_recording.channel == 1
    assert str(session_recording.start_original) == "2026-01-01 12:00:00"
    assert str(session_recording.end_original) == "2026-01-01 12:00:20"
    assert session_recording.duration_ms == 20_000

    metadata = {
        m.key: m.value
        for m in db.query(RecordingMetadata)
        .filter(RecordingMetadata.recording_id == session_recording.id)
        .all()
    }
    assert metadata["session_link_status"] == "continuous"
    assert metadata["segment_count"] == "2"
    segments = json.loads(metadata["source_segments"])
    assert [s["evidence_pk"] for s in segments] == [seg1.id, seg2.id]


def test_link_session_is_idempotent(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    seg1 = _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _synthetic_cpv_bytes(start_counter=100, end_counter=200, with_video=True),
    )
    seg2 = _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120010_20260101120020.cpv",
        _synthetic_cpv_bytes(start_counter=200, end_counter=300, with_video=True),
    )

    first = RecordingManager.link_session(db, [seg1.id, seg2.id])
    second = RecordingManager.link_session(db, [seg1.id, seg2.id])

    assert first.id == second.id
    assert db.query(Recording).filter(Recording.recording_id.startswith("SESSION-")).count() == 1


def test_link_session_rejects_segments_from_different_cases(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case1 = _make_case(db, "CASE-1")
    case2 = _make_case(db, "CASE-2")
    seg1 = _register_evidence(
        db,
        case1,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _synthetic_cpv_bytes(start_counter=100, end_counter=200, with_video=True),
    )
    seg2 = _register_evidence(
        db,
        case2,
        evidence_root,
        "NVR_ch1_main_20260101120010_20260101120020.cpv",
        _synthetic_cpv_bytes(start_counter=200, end_counter=300, with_video=True),
    )
    with pytest.raises(ValueError, match="different case"):
        RecordingManager.link_session(db, [seg1.id, seg2.id])


def test_link_session_rejects_a_non_cp_plus_segment(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    seg1 = _register_evidence(
        db,
        case,
        evidence_root,
        "NVR_ch1_main_20260101120000_20260101120010.cpv",
        _synthetic_cpv_bytes(start_counter=100, end_counter=200, with_video=True),
    )
    seg2 = _register_evidence(db, case, evidence_root, "not_cpv.bin", b"garbage")
    with pytest.raises(ValueError, match="does not match a supported CP Plus structure"):
        RecordingManager.link_session(db, [seg1.id, seg2.id])


# --- extract_recording ---


def test_extract_recording_with_no_video_data_reports_failed_status(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    content = _synthetic_cpv_bytes(start_counter=1, end_counter=2, with_video=False)
    evidence = _register_evidence(
        db, case, evidence_root, "NVR_ch1_main_20260101120000_20260101120010.cpv", content
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    result = RecordingManager.extract_recording(db, recording.id)

    assert result.artifact_id is None
    status = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == result.id,
            RecordingMetadata.key == "extraction_status",
        )
        .first()
    )
    assert status is not None
    assert status.value == "failed"


def test_extract_recording_raises_for_missing_recording(db_session_and_engine):
    db, _evidence_root = db_session_and_engine
    with pytest.raises(ValueError, match="not found"):
        RecordingManager.extract_recording(db, 999)
