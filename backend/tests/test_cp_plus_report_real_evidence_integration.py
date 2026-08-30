"""Real CP Plus evidence -- Phase 18 acceptance test.

Builds the same real Phase 9 extraction + Phase 15 provenance + Phase 16
audit chain + Phase 17 blockchain anchor pipeline as
`tests/test_cp_plus_provenance_real_evidence_integration.py`, then
generates a standardized JSON + PDF report from that real case state
(task Phase 18 scope section 32) and verifies:

- CP Plus identification/CPV extraction outputs appear
- source evidence integrity remains intact after report generation
- the unresolved CPV raw timestamp is NOT described as verified
- real AI results, when present, are referenced (none are run here --
  Phase 13 is not exercised by this fixture, so the AI section is
  legitimately empty; this is asserted explicitly rather than assumed)
- provenance/audit information appears
- the blockchain section correctly reports LOCAL/TEST (no real network
  is configured for this test run)
- limitations remain visible, never suppressed

Never puts CPV/video content on-chain or in the report body beyond
metadata/paths/hashes already established by prior phases.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader
import io

from app.adapters.cp_plus import PARSER_VERSION
from app.audit import ActorType, ProcessingOperation
from app.blockchain.provider import LocalTestBlockchainProvider
from app.config import get_settings
from app.core.blockchain_manager import BlockchainManager
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.provenance_manager import ProvenanceManager
from app.core.recording_manager import RecordingManager
from app.core.report_manager import ReportManager
from app.hashing.sha256 import sha256_file
from app.models import JobStatus, RecordingMetadata
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from tests.fixtures.cp_plus_evidence import requires_real_evidence, smallest_real_cpv_path


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    evidence_root = tmp_path / "evidence"
    artifact_root = tmp_path / "artifacts"
    report_root = tmp_path / "reports"
    evidence_root.mkdir()
    artifact_root.mkdir()
    report_root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("REPORT_ROOT", str(report_root))
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
def test_real_cp_plus_case_report_generation(real_evidence_db) -> None:
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    sha256_before = sha256_file(source_path)

    case_dir = evidence_root / "CASE-REPORT"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)
    copied_sha256_before = sha256_file(copied_path)

    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-REPORT", name="Report IT"))
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
    )
    recording = RecordingManager.extract_recording(db, recording.id)
    assert recording.artifact_id is not None

    preview_row = (
        db.query(RecordingMetadata)
        .filter(
            RecordingMetadata.recording_id == recording.id,
            RecordingMetadata.key == "preview_artifact_id",
        )
        .first()
    )
    assert preview_row is not None
    ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.EXTRACTION.value,
        actor="RecordingManager",
        actor_type=ActorType.SYSTEM,
        tool="ffmpeg",
        output_artifact_ids=[int(recording.artifact_id), int(preview_row.value)],
        status=JobStatus.COMPLETED,
        description="muxed H.265 master and transcoded H.264 preview",
    )

    provider = LocalTestBlockchainProvider()
    BlockchainManager.create_anchor(db, case_id=case.id, provider=provider, reason="report_test")

    reports = ReportManager.generate_report(db, case_id=case.id, formats=("json", "pdf"))
    json_report = next(r for r in reports if r.report_type == "json")
    pdf_report = next(r for r in reports if r.report_type == "pdf")

    parsed = json.loads(ReportManager.read_report_content(json_report))

    # CP Plus identification / CPV extraction outputs appear.
    assert parsed["recordings"], "recording section must be populated"
    recording_entry = parsed["recordings"][0]
    assert recording_entry["master_artifact_type"] == "cp_plus_hevc_master_mp4"
    assert recording_entry["preview_artifact_type"] == "cp_plus_h264_preview_mp4"
    assert any(p["tool"] == "CPPlusParser" for p in parsed["provenance"] if p["tool"] is not None)

    # The raw CP Plus timestamp is never claimed as verified: if the
    # parser marked it unresolved, the report's limitations section must
    # say so explicitly, and no limitation text claims verification.
    raw_status = recording_entry["metadata_entries"].get("timestamp_status")
    if raw_status and "unvalidated" in raw_status.lower():
        timestamp_limitations = [
            lim for lim in parsed["limitations"] if lim["category"] == "timestamp"
        ]
        assert timestamp_limitations
        for lim in timestamp_limitations:
            assert "not been independently verified" in lim["description"]
    assert parsed["recordings"][0]["start_original"] is not None

    # No real AI results were generated by this fixture -- assert that
    # honestly rather than assuming.
    assert parsed["ai"]["detections"] == []

    # Provenance/audit information appears.
    assert len(parsed["provenance"]) >= 3
    assert parsed["audit"]["valid"] is True
    assert parsed["audit"]["event_count"] >= 3

    # Blockchain section correctly reports LOCAL/TEST, not a real network.
    assert len(parsed["blockchain"]) == 1
    assert parsed["blockchain"][0]["is_real_network"] is False
    assert parsed["blockchain"][0]["provider"] == "local_testnet"

    # Limitations remain visible.
    assert parsed["limitations"]

    # PDF is valid and non-empty, and does not claim a real network.
    pdf_bytes = ReportManager.read_report_content(pdf_report)
    assert pdf_bytes.startswith(b"%PDF-")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "REAL NETWORK" not in pdf_text
    assert "LOCAL/TEST PROVIDER" in pdf_text

    # Source evidence remains provably unmodified by report generation.
    assert sha256_file(copied_path) == copied_sha256_before
    assert sha256_file(source_path) == sha256_before
