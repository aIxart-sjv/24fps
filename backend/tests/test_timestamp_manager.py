"""Tests for app/core/timestamp_manager.py (Phase 11), against small
synthetic CP Plus fixtures — fast, no real evidence required. The real-
evidence acceptance test lives in
tests/test_cp_plus_timestamp_real_evidence_integration.py.
"""

from __future__ import annotations

import datetime
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
from app.core.timestamp_manager import TimestampManager
from app.models import Case, Recording, RecordingMetadata
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from app.timeline import NormalizationMethod, NormalizationStatus, ReferencePair, TimestampSource

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


def _synthetic_cpv_bytes(*, start_counter: int = 100, end_counter: int = 103) -> bytes:
    return _outer_header_bytes(start_counter, end_counter) + _record_bytes(
        0xFD, start_counter, _keyframe_marker_body()
    )


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


def _register_cp_plus_recording(db: Session, case: Case, evidence_root: Path) -> Recording:
    filename = "NVR_ch1_main_20260828162000_20260828162002.cpv"
    path = evidence_root / filename
    path.write_bytes(_synthetic_cpv_bytes())
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=Path(filename).stem, source_type="native_export", source_path=str(path)
        ),
    )
    return RecordingManager.enumerate_recordings(db, evidence.id)[0]


def _reference(offset_seconds: float = 5.0) -> ReferencePair:
    return ReferencePair(
        reference_timestamp=datetime.datetime(2026, 8, 28, 16, 20)
        + datetime.timedelta(seconds=offset_seconds),
        reference_timezone="Asia/Kolkata",
        reference_source="examiner-recorded reference event",
        reference_basis="examiner observed NVR display next to a synced phone clock",
        method=NormalizationMethod.EXPLICIT_DVR_CLOCK_COMPARISON,
    )


def test_no_inputs_at_all_is_unknown_and_leaves_normalized_null(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    recording = _register_cp_plus_recording(db, case, evidence_root)

    outcome = TimestampManager.normalize_recording(db, recording.id)

    assert outcome.overall_status == NormalizationStatus.UNKNOWN
    assert outcome.recording.start_normalized is None
    assert outcome.recording.end_normalized is None


def test_source_timezone_alone_yields_unverified(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    recording = _register_cp_plus_recording(db, case, evidence_root)

    outcome = TimestampManager.normalize_recording(
        db,
        recording.id,
        source_timezone="Asia/Kolkata",
        source_timezone_basis="case device fact sheet",
    )

    assert outcome.overall_status == NormalizationStatus.UNVERIFIED
    assert outcome.start_result.source == TimestampSource.FILENAME_DERIVED
    # NormalizationResult itself carries full UTC tzinfo...
    assert outcome.start_result.normalized_timestamp == datetime.datetime(
        2026, 8, 28, 10, 50, 0, tzinfo=datetime.UTC
    )
    # ...but SQLite's DateTime(timezone=True) does not round-trip tzinfo
    # (a pre-existing characteristic of every such column in this schema,
    # not introduced by this phase) — the stored/reloaded value is naive
    # but numerically UTC.
    assert outcome.recording.start_normalized == datetime.datetime(2026, 8, 28, 10, 50, 0)


def test_reference_yields_verified_and_applies_same_offset_to_both_ends(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    recording = _register_cp_plus_recording(db, case, evidence_root)

    outcome = TimestampManager.normalize_recording(
        db, recording.id, source_timezone="Asia/Kolkata", reference=_reference(5.0)
    )

    assert outcome.overall_status == NormalizationStatus.VERIFIED
    assert outcome.start_result.offset_seconds == 5.0
    assert outcome.end_result.offset_seconds == 5.0  # same offset, not re-derived
    # start_original 16:20:00, end_original 16:20:02 -> 2s gap preserved after +5s each.
    assert (outcome.recording.end_normalized - outcome.recording.start_normalized) == (
        datetime.timedelta(seconds=2)
    )


def test_original_timestamps_are_never_overwritten(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    recording = _register_cp_plus_recording(db, case, evidence_root)
    original_start = recording.start_original
    original_end = recording.end_original

    TimestampManager.normalize_recording(
        db, recording.id, source_timezone="Asia/Kolkata", reference=_reference(5.0)
    )

    db.refresh(recording)
    assert recording.start_original == original_start
    assert recording.end_original == original_end


def test_rerun_with_weaker_inputs_clears_stale_normalized_values(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    recording = _register_cp_plus_recording(db, case, evidence_root)

    TimestampManager.normalize_recording(
        db, recording.id, source_timezone="Asia/Kolkata", reference=_reference(5.0)
    )
    outcome = TimestampManager.normalize_recording(db, recording.id)  # no inputs this time

    assert outcome.overall_status == NormalizationStatus.UNKNOWN
    assert outcome.recording.start_normalized is None
    assert outcome.recording.end_normalized is None


def test_metadata_provenance_rows_are_written(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    recording = _register_cp_plus_recording(db, case, evidence_root)

    TimestampManager.normalize_recording(
        db,
        recording.id,
        source_timezone="Asia/Kolkata",
        source_timezone_basis="case device fact sheet",
        reference=_reference(5.0),
    )

    rows = {
        m.key: m.value
        for m in db.query(RecordingMetadata)
        .filter(RecordingMetadata.recording_id == recording.id)
        .all()
    }
    assert rows["timestamp_normalization_status"] == "verified"
    assert rows["timestamp_normalization_source"] == "filename_derived"
    assert rows["timestamp_source_timezone"] == "Asia/Kolkata"
    assert rows["timestamp_source_timezone_basis"] == "case device fact sheet"
    assert rows["timestamp_offset_seconds"] == "5.0"
    assert rows["timestamp_reference_source"] == "examiner-recorded reference event"


def test_raw_cpv_binary_timestamp_metadata_is_never_touched(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    recording = _register_cp_plus_recording(db, case, evidence_root)

    raw_before = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "timestamp_status",
        )
        .first()
    )
    assert raw_before is not None
    assert raw_before.value == "raw_counter_unvalidated"

    TimestampManager.normalize_recording(
        db, recording.id, source_timezone="Asia/Kolkata", reference=_reference(5.0)
    )

    raw_after = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "timestamp_status",
        )
        .first()
    )
    assert raw_after.value == "raw_counter_unvalidated"  # untouched


def test_raises_for_missing_recording(db_session_and_engine):
    db, _evidence_root = db_session_and_engine
    with pytest.raises(ValueError, match="not found"):
        TimestampManager.normalize_recording(db, 999)


def test_resolve_timestamp_error_none_without_verified_normalization(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    recording = _register_cp_plus_recording(db, case, evidence_root)

    assert TimestampManager.resolve_timestamp_error(db, recording) is None

    TimestampManager.normalize_recording(db, recording.id, source_timezone="Asia/Kolkata")
    assert (
        TimestampManager.resolve_timestamp_error(db, recording) is None
    )  # UNVERIFIED, not VERIFIED


def test_resolve_timestamp_error_returns_offset_magnitude_when_verified(db_session_and_engine):
    db, evidence_root = db_session_and_engine
    case = _make_case(db)
    recording = _register_cp_plus_recording(db, case, evidence_root)

    TimestampManager.normalize_recording(
        db, recording.id, source_timezone="Asia/Kolkata", reference=_reference(-5.0)
    )
    assert TimestampManager.resolve_timestamp_error(db, recording) == 5.0  # abs() of -5.0
