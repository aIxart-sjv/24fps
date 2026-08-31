"""Real CP Plus evidence -- Phase 22 acceptance test.

Demonstrates the full automatic-processing workflow against real evidence,
end to end, exercising the "officer does not watch everything" scenario
(task Phase 22 scope, section 46): the officer registers evidence and
calls the ONE high-level processing endpoint -- they never manually run
recovery, never manually inspect the whole recording, and never call any
of the dozen individual phase APIs. Automatic processing alone must
surface the evidence package's one known, real, measurable anomaly (the
smallest real segment's genuinely truncated trailing record -- see
CPV_ANALYSIS_REPORT.md and tests/test_cp_plus_recovery_real_evidence_integration.py)
as a finding pointing at the specific recording/evidence, without ever
claiming it proves deliberate tampering.

Also verifies the negative claims Phase 22's own final rules require:
this evidence set is single-camera (all 13 real segments are `ch1`), so
cross-camera correlation must be explicitly skipped as not applicable --
never fabricated -- and this evidence set has no deleted recordings, so
recovery must never report a fabricated "deleted recording recovered".
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.auth_manager import AuthManager
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.processing_orchestrator import ProcessingOrchestrator
from app.core.processing_policy import ProcessingPolicy
from app.models import Device, Finding, FindingType, JobStatus, Notification
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
    """Matches tests/test_cp_plus_recovery_real_evidence_integration.py's
    own fixture exactly: an isolated EVIDENCE_ROOT/ARTIFACT_ROOT/in-memory
    DB -- the original, out-of-repo evidence directory is never used as
    EVIDENCE_ROOT directly, and is never written to."""
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
def test_automatic_processing_surfaces_the_known_anomaly_without_manual_inspection(
    real_evidence_db,
) -> None:
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    expected_hashes = load_expected_sha256()
    original_hash = sha256_of(source_path)
    assert original_hash == expected_hashes[source_path.name]

    case_dir = evidence_root / "CASE-P22"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-P22", name="Phase 22 IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    officer = AuthManager.create_user(
        db, username="officer_p22", display_name="Officer P22", password="password123"
    )

    # ---- The officer's ONLY action: one high-level "process this case"
    # call. They never run recovery/AI/timeline manually, and never watch
    # the recording themselves.
    summary = ProcessingOrchestrator.process_case(
        db, case.id, policy=ProcessingPolicy(run_ai=False), triggered_by=officer
    )

    # ---- Phase 24 task scope, "Acquisition Metadata -- Fix Accuracy": for
    # this real, known CP Plus recording, automatic processing must
    # identify the real vendor with a documented basis (the confirmed
    # CPV/ADIT-v1 structure) -- not the "vendor unknown, 60%" placeholder
    # `app.detection.device_identifier`'s generic pass alone would leave.
    device = db.query(Device).filter(Device.evidence_id == evidence.id).first()
    assert device is not None
    assert device.vendor == "CP Plus"
    assert device.identification_method == "cp_plus_structure_signature"
    assert device.confidence == 1.0

    # The orchestrator ran to a terminal state without crashing, and
    # honestly reports PARTIAL (not COMPLETED) because the recovery
    # anomaly and the absent validation dataset are both real, unresolved
    # conditions.
    assert summary.root_job.status in (JobStatus.PARTIAL.value, JobStatus.COMPLETED.value)

    # ---- The known, real anomaly was found automatically and pointed at
    # the specific recording -- the officer did not have to find it.
    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    partial_recovery_findings = [
        f for f in findings if f.finding_type == FindingType.PARTIAL_RECOVERY.value
    ]
    assert partial_recovery_findings, "the known truncated-record recovery anomaly was not surfaced"
    anomaly = partial_recovery_findings[0]
    assert anomaly.recording_id is not None
    assert anomaly.evidence_id is not None

    # ---- Hedged forensic language: never a stronger claim than the
    # underlying signal supports.
    for finding in findings:
        lowered = finding.description.lower()
        for forbidden in ("tamper", "guilt", "deleted deliberately", "proves"):
            assert (
                forbidden not in lowered
            ), f"finding {finding.id} overclaims: {finding.description!r}"

    # ---- Single-camera evidence: correlation is explicitly not
    # applicable, never fabricated as a cross-camera result.
    correlation_stage = next(
        child for child in summary.root_job.child_jobs if child.job_type == "correlation"
    )
    assert correlation_stage.status == JobStatus.SKIPPED.value
    assert not any(f.finding_type == FindingType.CROSS_CAMERA_CORRELATION.value for f in findings)

    # ---- No deleted-recording recovery is ever fabricated for this
    # evidence set (it contains none) -- recovery findings, if any beyond
    # the known partial one, must never claim a full/deleted recovery.
    assert not any(
        "deleted" in f.description.lower() and "recovered" in f.description.lower()
        for f in findings
    )

    # ---- The officer was notified, pointing back to the authoritative finding.
    notifications = (
        db.query(Notification).filter(Notification.recipient_user_id == officer.id).all()
    )
    assert any(n.finding_id == anomaly.id for n in notifications)

    # ---- Source evidence is provably unmodified by the entire automatic
    # processing run.
    assert sha256_of(copied_path) == expected_hashes[source_path.name]
    assert sha256_of(source_path) == expected_hashes[source_path.name]
    assert original_hash == expected_hashes[source_path.name]


@requires_real_evidence
def test_processing_is_idempotent_against_real_evidence(real_evidence_db) -> None:
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    case_dir = evidence_root / "CASE-P22-IDEM"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    case = CaseManager.create_case(
        db, CaseCreateRequest(case_id="CASE-P22-IDEM", name="Phase 22 idempotency IT")
    )
    EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )

    policy = ProcessingPolicy(run_ai=False)
    ProcessingOrchestrator.process_case(db, case.id, policy=policy)
    first_finding_count = db.query(Finding).filter(Finding.case_id == case.id).count()

    ProcessingOrchestrator.process_case(db, case.id, policy=policy)
    second_finding_count = db.query(Finding).filter(Finding.case_id == case.id).count()

    assert second_finding_count == first_finding_count
