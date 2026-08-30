"""Real CP Plus evidence — Phase 10 acceptance test.

Demonstrates the full Phase 10 pipeline against real evidence, end to end:

    CP Plus evidence
      -> Phase 8 parser
      -> Phase 9 extraction structures
      -> Phase 10 recovery engine
      -> recovery decision
      -> derived artifact
      -> hash
      -> traceability

using the real evidence package's own genuinely truncated trailing record
(the smallest segment's second KEYFRAME_MARKER record — see
CPV_ANALYSIS_REPORT.md and tests/test_cp_plus_real_evidence_integration.py)
as the one real damaged-recording condition this evidence set actually
contains.

CRITICAL, per the Phase 10 task's own instruction: the real evidence
package contains **no deleted recordings**. This file does not claim
otherwise anywhere, and explicitly asserts the literal "not validated"
statement `find_deleted_recordings` reports.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from app.adapters.cp_plus import CPPlusAdapter
from app.adapters.cp_plus.recovery import DELETED_RECOVERY_NOT_VALIDATED_STATEMENT
from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.core.recovery_manager import RecoveryManager
from app.models import Artifact
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from tests.fixtures.cp_plus_evidence import (
    load_expected_sha256,
    requires_real_evidence,
    sha256_of,
    smallest_real_cpv_path,
)


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Copies the real, smallest CP Plus segment into an isolated EVIDENCE_ROOT
    (the original, out-of-repo evidence directory is never used as
    EVIDENCE_ROOT directly, and is never written to) plus an isolated
    in-memory DB/ARTIFACT_ROOT, matching the established root-override
    pattern from tests/test_recording_manager.py.
    """
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
def test_full_pipeline_real_truncated_segment_recovers_partial(real_evidence_db):
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    expected_hashes = load_expected_sha256()
    assert sha256_of(source_path) == expected_hashes[source_path.name]

    case_dir = evidence_root / "CASE-REC"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-REC", name="Recovery IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )

    # Phase 8 parser -> Phase 9 extraction structures: enumerate first.
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]

    # Phase 10 recovery engine -> recovery decision -> derived artifact -> hash.
    result = RecoveryManager.run_recovery(db, recording.id)

    assert result.status == "partial"  # the real, known truncated-record condition
    assert result.method == "vendor_damaged_recovery"
    assert result.frames_recovered is not None and result.frames_recovered > 0
    assert result.frame_continuity == pytest.approx(1.0)
    assert "truncated" in (result.notes or "")

    # Derived artifact + hash + traceability.
    assert result.artifact_id is not None
    artifact = db.query(Artifact).filter(Artifact.id == result.artifact_id).first()
    assert artifact is not None
    assert artifact.evidence_id == evidence.id
    recovered_bytes = Path(artifact.path).read_bytes()
    assert len(recovered_bytes) > 0
    assert artifact.sha256 == hashlib.sha256(recovered_bytes).hexdigest()
    assert result.evidence_id == evidence.id
    assert result.recording_id == recording.id

    # The derived artifact is stored under ARTIFACT_ROOT, never EVIDENCE_ROOT.
    assert str(evidence_root) not in artifact.path or "artifacts" in Path(artifact.path).parts

    # Source evidence is provably unmodified by the entire pipeline.
    assert sha256_of(copied_path) == expected_hashes[source_path.name]
    assert sha256_of(source_path) == expected_hashes[source_path.name]


@requires_real_evidence
def test_deleted_recording_recovery_is_explicitly_not_validated_on_real_evidence():
    """Task section 15: explicit, literal reporting when real deleted-record
    evidence is unavailable — never a fabricated success."""
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    from app.acquisition.storage_reader import FileBackedReader

    with FileBackedReader(source_path) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id=source_path.stem)
        result = adapter.find_deleted_recordings()

    assert result.metadata["recovery_status"] == "unsupported"
    assert DELETED_RECOVERY_NOT_VALIDATED_STATEMENT in result.warnings[0]


@requires_real_evidence
def test_carving_on_real_evidence_finds_nothing_beyond_sequential_walk(real_evidence_db):
    """Honest scope check (Phase 10 task, carving section): our real evidence
    is 13 already-delineated, structurally intact files, not raw/
    unallocated storage — carving has nothing extra to find here. The
    synthetic "carving survives a corrupted middle record" case is proven
    separately in tests/test_recovery_carving.py."""
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None
    case_dir = evidence_root / "CASE-CARVE"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-CARVE", name="Carving IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]
    result = RecoveryManager.run_recovery(db, recording.id)

    assert "carving: no_recovery_found" in (result.notes or "")
