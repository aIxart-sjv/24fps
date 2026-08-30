"""Real CP Plus evidence — Phase 11 acceptance test.

Demonstrates the full Phase 11 pipeline against real evidence, end to end:

    original/source timestamp (filename-derived)
      -> source classification
      -> [no reference in this evidence package]
      -> examiner-supplied source timezone (Asia/Kolkata, from the case's
         known device fact sheet)
      -> UNVERIFIED normalized timestamp
      -> original preserved

and, separately, the unresolved CPV binary counter path:

    raw timestamp
      -> preserved
      -> not incorrectly converted
      -> UNKNOWN / not used as a normalization input

CRITICAL, per the Phase 11 task's own instruction: this evidence package
has no independently-verified external reference-clock pair, so the real,
honest outcome here is UNVERIFIED, never VERIFIED. This file does not
claim the CP Plus binary timestamp field is solved, and applies no 24-hour
correction, no guessed epoch, and no fabricated reference.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.core.timestamp_manager import TimestampManager
from app.models import RecordingMetadata
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from app.timeline import NormalizationMethod, NormalizationStatus, ReferencePair
from tests.fixtures.cp_plus_evidence import (
    load_expected_sha256,
    requires_real_evidence,
    sha256_of,
    smallest_real_cpv_path,
)


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Matches the established pattern from
    tests/test_cp_plus_recovery_real_evidence_integration.py."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

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
    import app.models  # noqa: F401 - registers every ORM model on Base.metadata

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


@requires_real_evidence
def test_filename_derived_original_normalizes_to_unverified_with_examiner_timezone(
    real_evidence_db,
):
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    expected_hashes = load_expected_sha256()
    assert sha256_of(source_path) == expected_hashes[source_path.name]

    case_dir = evidence_root / "CASE-TS"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-TS", name="Timestamp IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    original_start = recording.start_original
    original_end = recording.end_original
    assert original_start is not None  # the real, known filename-derived interval

    # No reference pair exists in this evidence package — only the
    # examiner-supplied source timezone (the case's known device fact
    # sheet: CP-UNR-108F1 is configured for IST), matching task Phase 11
    # scope section 5's explicit guidance to use that fact only as
    # evidence for *this* case, never hardcoded into the engine.
    outcome = TimestampManager.normalize_recording(
        db,
        recording.id,
        source_timezone="Asia/Kolkata",
        source_timezone_basis=(
            "case device fact sheet: CP-UNR-108F1 (firmware V1.00.14.01.R) is configured for IST"
        ),
    )

    # The honest, real outcome: UNVERIFIED, never VERIFIED — no trustworthy
    # reference exists in this evidence package.
    assert outcome.overall_status == NormalizationStatus.UNVERIFIED
    assert outcome.start_result.method == NormalizationMethod.TIMEZONE_CONVERSION
    assert outcome.recording.start_normalized is not None
    assert outcome.recording.end_normalized is not None

    # Original values are provably unchanged.
    db.refresh(recording)
    assert recording.start_original == original_start
    assert recording.end_original == original_end

    # Full provenance is recorded and inspectable.
    rows = {
        m.key: m.value
        for m in db.query(RecordingMetadata)
        .filter(RecordingMetadata.recording_id == recording.id)
        .all()
    }
    assert rows["timestamp_normalization_status"] == "unverified"
    assert rows["timestamp_normalization_source"] == "filename_derived"
    assert rows["timestamp_source_timezone"] == "Asia/Kolkata"
    assert "timestamp_offset_seconds" not in rows  # never fabricated

    # Source evidence file is provably unmodified by the entire pipeline.
    assert sha256_of(copied_path) == expected_hashes[source_path.name]
    assert sha256_of(source_path) == expected_hashes[source_path.name]


@requires_real_evidence
def test_raw_cpv_binary_counter_stays_unresolved_never_converted(real_evidence_db):
    """The critical CP Plus finding (task Phase 11 scope, section 3): the raw
    CPV binary timestamp-like field must remain preserved, unresolved, and
    is never used as a normalization input — no guessed epoch, no 24-hour
    correction, no promotion to an authoritative timestamp."""
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None
    case_dir = evidence_root / "CASE-RAW"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-RAW", name="Raw TS IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    raw_before = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "raw_timestamp",
        )
        .first()
    )
    status_before = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "timestamp_status",
        )
        .first()
    )
    assert raw_before is not None  # the real, evidence-validated raw counter is preserved
    assert status_before.value == "raw_counter_unvalidated"

    # Run normalization with every possible input, including a (deliberately
    # unrelated/untrustworthy-looking) reference — even so, the raw binary
    # counter is never read as an input, so it stays exactly as Phase 8/9
    # left it.
    fabricated_reference = ReferencePair(
        reference_timestamp=recording.start_original,
        reference_timezone="Asia/Kolkata",
        reference_source="test-only reference",
        reference_basis="synthetic, for this test only",
    )
    TimestampManager.normalize_recording(
        db, recording.id, source_timezone="Asia/Kolkata", reference=fabricated_reference
    )

    raw_after = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "raw_timestamp",
        )
        .first()
    )
    status_after = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "timestamp_status",
        )
        .first()
    )
    assert raw_after.value == raw_before.value  # byte-for-byte unchanged
    assert status_after.value == "raw_counter_unvalidated"  # still unresolved

    # And it never leaked into normalization's own recorded source.
    source_row = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "timestamp_normalization_source",
        )
        .first()
    )
    assert source_row.value == "filename_derived"
    assert source_row.value != "cpv_binary_timestamp"


@requires_real_evidence
def test_no_reference_and_no_timezone_is_explicitly_unknown_not_a_guess(real_evidence_db):
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None
    case_dir = evidence_root / "CASE-UNK"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-UNK", name="Unknown TS IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    outcome = TimestampManager.normalize_recording(db, recording.id)

    assert outcome.overall_status == NormalizationStatus.UNKNOWN
    assert outcome.recording.start_normalized is None
    assert outcome.recording.end_normalized is None
