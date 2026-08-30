"""Real CP Plus evidence -- Phase 14 acceptance test.

Validates the portions of the pipeline that genuinely have ground truth
for this evidence package: the CPV file is recognized, its recordings
enumerate, extraction is compatible (a derived MP4 was actually produced),
and the source evidence file is provably unmodified by the entire
pipeline (Master Specification Section 51 rule 7-adjacent: validation
must never overwrite source evidence).

This evidence package (`~/Documents/24fps-evidence/cp-plus-2026-08-28/`)
has never been independently annotated with object/face/motion ground
truth (no examiner has marked "a person appears at frame N" against this
real footage) -- task Phase 14 scope section 30's own explicit
instruction: "If object/face/motion ground truth has not been
independently annotated: do not report an accuracy number for that real
dataset." This file states that plainly rather than fabricating such
ground truth, exactly as Phase 12/13's own real-evidence tests state their
equivalent real-data scope limits.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.core.validation_manager import ValidationManager
from app.models import JobStatus
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from tests.fixtures.cp_plus_evidence import (
    load_expected_sha256,
    requires_real_evidence,
    sha256_of,
    smallest_real_cpv_path,
)

#: This evidence package has no independently-annotated object/face/
#: motion ground truth -- stated explicitly rather than fabricated.
REAL_AI_GROUND_TRUTH_STATEMENT = (
    "No object/face/motion ground truth has been independently annotated "
    "for this real CP Plus footage; only structural/parser validation "
    "(file recognition, record structure, enumeration, extraction "
    "compatibility, source integrity) is reported against it."
)


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Matches the established pattern from
    tests/test_cp_plus_ai_real_evidence_integration.py."""
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


def test_real_ai_ground_truth_scope_is_explicitly_pending() -> None:
    assert "No object/face/motion ground truth" in REAL_AI_GROUND_TRUTH_STATEMENT
    assert "independently annotated" in REAL_AI_GROUND_TRUTH_STATEMENT


@requires_real_evidence
def test_real_recording_vendor_parser_validation(real_evidence_db) -> None:
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    expected_hashes = load_expected_sha256()
    assert sha256_of(source_path) == expected_hashes[source_path.name]

    case_dir = evidence_root / "CASE-VALIDATION"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-VALIDATION", name="Val IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]
    recording = RecordingManager.extract_recording(db, recording.id)

    # Ground truth for this real, known evidence file: we independently
    # know it is a real CP Plus recording that should be recognized,
    # enumerate to exactly one recording, and be extraction-compatible --
    # this is genuinely independent knowledge (the fixture's own
    # documented, hash-verified evidence package description), not a
    # value copied from the pipeline's own output.
    ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-REAL-CPPLUS",
        event_type="vendor_parser",
        recording_id=recording.id,
        source_reference=(
            "real CP Plus evidence package (~/Documents/24fps-evidence/"
            "cp-plus-2026-08-28/), hash-verified via SHA256SUMS.txt"
        ),
        notes="expected: file recognized, one recording enumerated, extraction-compatible",
    )

    job, metrics = ValidationManager.run_validation(
        db, case_id=case.id, validation_type="vendor_parser", dataset_id="DS-REAL-CPPLUS"
    )

    assert job.status == JobStatus.COMPLETED.value
    values = {m.metric_name: m.metric_value for m in metrics}
    prefix = f"vendor_parser.recording_{recording.id}."
    assert values[f"{prefix}file_recognized"] == 1.0
    assert values[f"{prefix}recording_enumerated"] == 1.0
    assert values[f"{prefix}extraction_compatible"] == 1.0

    # Validation never modifies source evidence.
    assert sha256_of(copied_path) == expected_hashes[source_path.name]
    assert sha256_of(source_path) == expected_hashes[source_path.name]
