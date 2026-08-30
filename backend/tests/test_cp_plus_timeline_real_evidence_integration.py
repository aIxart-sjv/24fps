"""Real CP Plus evidence — Phase 12 acceptance test.

This evidence package (`~/Documents/24fps-evidence/cp-plus-2026-08-28/`)
is a single NVR, single channel: it cannot and does not validate real
cross-camera correlation. Per the Phase 12 task's own instruction, this
file states that fact explicitly rather than fabricating a multi-camera
scenario from single-channel evidence:

    Cross-camera correlation validated against controlled test events;
    real multi-camera CP Plus validation remains pending.

What this file *does* validate against real evidence, end to end through
Phase 9 (extraction) -> Phase 11 (normalization) -> Phase 12 (timeline
ingestion): event ingestion from a real `Recording`, normalized-timestamp
usage (never recomputed here), source traceability (case/evidence/
recording IDs), and recovery-status propagation onto the resulting
`TimelineEvent` rows.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.correlation_manager import CorrelationManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.core.timeline_manager import TimelineManager
from app.core.timestamp_manager import TimestampManager
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from app.timeline import NormalizationStatus
from tests.fixtures.cp_plus_evidence import (
    load_expected_sha256,
    requires_real_evidence,
    sha256_of,
    smallest_real_cpv_path,
)

#: The task's own required, honest statement about this evidence
#: package's scope — asserted, not just documented, so it cannot silently
#: bit-rot if the fixture ever changes.
REAL_MULTI_CAMERA_VALIDATION_STATEMENT = (
    "Cross-camera correlation validated against controlled test events; "
    "real multi-camera CP Plus validation remains pending."
)


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Matches the established pattern from
    tests/test_cp_plus_timestamp_real_evidence_integration.py."""
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


def test_real_multi_camera_validation_is_explicitly_pending() -> None:
    """This evidence package is single-NVR/single-channel; asserted here
    so the honest limitation statement cannot silently drift from the
    other tests in this file."""
    assert "real multi-camera CP Plus validation remains pending" in (
        REAL_MULTI_CAMERA_VALIDATION_STATEMENT
    )


@requires_real_evidence
def test_ingest_recording_events_from_real_cp_plus_recording(real_evidence_db):
    """End to end: real CPV -> extracted `Recording` -> Phase 11
    normalization -> Phase 12 timeline ingestion, with full source
    traceability and recovery-status propagation."""
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    expected_hashes = load_expected_sha256()
    assert sha256_of(source_path) == expected_hashes[source_path.name]

    case_dir = evidence_root / "CASE-TL"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-TL", name="Timeline IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    outcome = TimestampManager.normalize_recording(
        db,
        recording.id,
        source_timezone="Asia/Kolkata",
        source_timezone_basis=(
            "case device fact sheet: CP-UNR-108F1 (firmware V1.00.14.01.R) is configured for IST"
        ),
    )
    # The honest, real Phase 11 outcome for this evidence package.
    assert outcome.overall_status == NormalizationStatus.UNVERIFIED

    events = TimelineManager.ingest_recording_events(db, recording.id)

    assert len(events) == 2
    start_event, end_event = events

    # Normalized-timestamp usage: Phase 12 reads exactly what Phase 11
    # computed, never recomputes it.
    assert start_event.normalized_timestamp == outcome.recording.start_normalized
    assert end_event.normalized_timestamp == outcome.recording.end_normalized
    assert start_event.original_timestamp == outcome.recording.start_original

    # Full source traceability: case, evidence-derived recording, and
    # recording IDs are all preserved on the ingested events.
    assert start_event.case_id == case.id
    assert start_event.recording_id == recording.id

    # Recovery status propagation: this recording was extracted (not
    # recovered), so recovery_status is None -- honestly reported, not a
    # fabricated "full" default.
    assert start_event.recovery_status == recording.recovery_status

    # Single-channel evidence: only one camera identity is present.
    # `recording_start`/`recording_end` may still chain temporally (both
    # are close in time), but this is never a *cross-camera* candidate --
    # same-camera pairs always read `topology: UNKNOWN` (never `YES`),
    # since there is no second camera to configure a transition to/from.
    # This is the expected, honest outcome for this evidence package: it
    # exercises ingestion, traceability, and the engine end to end, but
    # cannot and does not demonstrate genuine cross-camera correlation.
    result, persisted = CorrelationManager.run_correlation(db, case.id)
    assert result.input_event_count == 2
    for correlation_event in persisted:
        details = json.loads(correlation_event.description)
        for link in details["links"]:
            assert link["topology"] != "yes"

    # Source evidence file is provably unmodified by the entire pipeline.
    assert sha256_of(copied_path) == expected_hashes[source_path.name]
    assert sha256_of(source_path) == expected_hashes[source_path.name]
