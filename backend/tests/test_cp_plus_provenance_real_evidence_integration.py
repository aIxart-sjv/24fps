"""Real CP Plus evidence -- Phase 15/16/17 acceptance test.

Runs the real, untouched Phase 9 extraction pipeline
(`RecordingManager.enumerate_recordings` + `extract_recording`) against
real CP Plus evidence, then explicitly records what happened via
`ProvenanceManager.record_event` (provenance links *existing* objects --
it never creates duplicate artifacts/recordings). Verifies that
traversal from the derived H.264 preview artifact reaches the original
evidence, and that the source evidence file's SHA-256, MD5, size, and
modification time are all provably unchanged by the entire pipeline
(extraction + provenance recording).

Also anchors the resulting real, valid Phase 16 chain (task Phase 17
scope section 32) using an explicit, in-memory
`LocalTestBlockchainProvider` -- never a real blockchain network (none
is configured for this test run; see the final report for how to read
that honestly). No CPV/video content is ever passed to the provider,
only the SHA-256 anchor hash of the chain state.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.adapters.cp_plus import PARSER_VERSION
from app.audit import ActorType, ProcessingOperation
from app.audit.hash_chain import ChainFailureReason
from app.blockchain.provider import LocalTestBlockchainProvider
from app.blockchain.verification import AnchorVerificationOutcome
from app.config import get_settings
from app.core.audit_chain_manager import AuditChainManager
from app.core.blockchain_manager import BlockchainManager
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.provenance_manager import ProvenanceManager
from app.core.recording_manager import RecordingManager
from app.hashing.md5 import md5_file
from app.hashing.sha256 import sha256_file
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


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Matches the established pattern from
    tests/test_cp_plus_validation_real_evidence_integration.py."""
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
def test_real_recording_extraction_provenance_and_source_immutability(real_evidence_db) -> None:
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    expected_hashes = load_expected_sha256()
    assert sha256_of(source_path) == expected_hashes[source_path.name]

    case_dir = evidence_root / "CASE-PROVENANCE"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    # Snapshot the case-local copy's integrity facts *before* running
    # anything -- these must be provably unchanged afterward.
    sha256_before = sha256_file(copied_path)
    md5_before = md5_file(copied_path)
    size_before = copied_path.stat().st_size
    mtime_before = copied_path.stat().st_mtime

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-PROVENANCE", name="Prov IT"))
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )

    ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation="evidence_registered",
        actor="EvidenceManager",
        actor_type=ActorType.SYSTEM,
        software_version=get_settings().app_version,
        status=JobStatus.COMPLETED,
    )

    recording = RecordingManager.enumerate_recordings(db, evidence.id)[0]
    ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.PARSING.value,
        actor="CPPlusParser",
        actor_type=ActorType.SYSTEM,
        tool="CPPlusParser",
        tool_version=PARSER_VERSION,
        status=JobStatus.COMPLETED,
        description=f"enumerated recording {recording.recording_id!r}",
    )

    recording = RecordingManager.extract_recording(db, recording.id)
    assert recording.artifact_id is not None  # the H.265 master artifact

    master_artifact_id = int(recording.artifact_id)
    from app.models import RecordingMetadata

    preview_row = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "preview_artifact_id",
        )
        .first()
    )
    assert preview_row is not None
    preview_artifact_id = int(preview_row.value)

    ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.EXTRACTION.value,
        actor="RecordingManager",
        actor_type=ActorType.SYSTEM,
        tool="ffmpeg",
        output_artifact_ids=[master_artifact_id, preview_artifact_id],
        status=JobStatus.COMPLETED,
        description="muxed H.265 master and transcoded H.264 preview",
    )

    # Provenance links existing objects -- it never duplicates them.
    source = ProvenanceManager.get_artifact_source(db, preview_artifact_id)
    assert source.id == evidence.id

    events_for_preview = ProvenanceManager.get_processing_events_for_artifact(
        db, preview_artifact_id
    )
    assert any(e.operation == "extraction" for e in events_for_preview)

    case_history = ProvenanceManager.get_case_history(db, case.id)
    assert [e.operation for e in case_history] == ["evidence_registered", "parsing", "extraction"]

    summary = ProvenanceManager.get_case_summary(db, case.id)
    assert summary.processing_event_count == 3
    assert "ffmpeg" in summary.tools_used
    assert "CPPlusParser" in summary.tools_used

    # Source evidence is provably unmodified by the entire pipeline,
    # including provenance recording itself.
    assert sha256_file(copied_path) == sha256_before
    assert md5_file(copied_path) == md5_before
    assert copied_path.stat().st_size == size_before
    assert copied_path.stat().st_mtime == mtime_before
    assert sha256_of(source_path) == expected_hashes[source_path.name]

    # Phase 16: the real 3-event chain built above verifies valid end-to-end.
    chain_result = AuditChainManager.verify_case_chain(db, case.id)
    assert chain_result.valid is True
    assert chain_result.event_count == 3
    assert chain_result.failure is None

    # Phase 17: anchor this real, valid chain state. A local/test
    # provider is used deliberately -- no real blockchain network is
    # configured or contacted in this test run (see the final report).
    blockchain_provider = LocalTestBlockchainProvider()
    anchor = BlockchainManager.create_anchor(
        db, case_id=case.id, provider=blockchain_provider, reason="real_evidence_integration_test"
    )
    assert anchor.provider == "local_testnet"
    assert anchor.transaction_reference.startswith("LOCAL-TEST-ANCHOR-")
    assert len(anchor.audit_state_hash) == 64

    anchor_check = BlockchainManager.verify_anchor(
        db, anchor_id=anchor.id, provider=blockchain_provider
    )
    assert anchor_check.valid is True
    assert anchor_check.outcome == AnchorVerificationOutcome.VALID

    # The anchor never received the CPV content or any forensic artifact
    # bytes -- only a SHA-256 fingerprint of the chain state.
    assert copied_path.name not in anchor.audit_state_hash
    assert len(anchor.audit_state_hash) == 64  # a hash, not a file payload

    # Tampering one recorded field on real-evidence-derived history is detected.
    from app.models import ProcessingEvent

    extraction_event = (
        db.query(ProcessingEvent)
        .filter(ProcessingEvent.case_id == case.id, ProcessingEvent.operation == "extraction")
        .first()
    )
    extraction_event.tool = "not-ffmpeg"
    db.commit()

    tampered_result = AuditChainManager.verify_case_chain(db, case.id)
    assert tampered_result.valid is False
    assert tampered_result.failure.event_id == extraction_event.id
    assert tampered_result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH

    # The same tamper is independently detected through the blockchain
    # anchor's own verification path -- the anchor itself is untouched
    # (never silently rewritten), but comparing against it now fails.
    tampered_anchor_check = BlockchainManager.verify_anchor(
        db, anchor_id=anchor.id, provider=blockchain_provider
    )
    assert tampered_anchor_check.valid is False
    assert tampered_anchor_check.outcome == AnchorVerificationOutcome.CHAIN_INVALID
    reloaded_anchor = BlockchainManager.get_anchor(db, anchor.id)
    assert reloaded_anchor.audit_state_hash == anchor.audit_state_hash
    assert reloaded_anchor.transaction_reference == anchor.transaction_reference

    # Tampering the copied evidence file itself is still a separate, orthogonal
    # fact from the audit chain -- confirm both remain independently true.
    assert sha256_file(copied_path) == sha256_before
