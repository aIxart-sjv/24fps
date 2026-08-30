"""Real CP Plus evidence -- Phase 21 Part A acceptance test.

Registers one real, hash-verified CP Plus `.cpv` file as an `Evidence`
row (the same registration path every other real-evidence test in this
suite uses) and runs the physical custody intake + QR handoff lifecycle
against its real `evidence_id`.

Custody *participants* (officers) are synthetic test users -- this test
never pretends the real physical CP Plus DVR/evidence file itself
changed hands; it verifies that Phase 21's custody tracking correctly
links to a real evidence item's identity and that the source file itself
is provably untouched by the custody workflow (custody metadata lives
entirely in `custody_transfers`/`processing_events`, never in the
evidence file).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.audit_chain_manager import AuditChainManager
from app.core.auth_manager import AuthManager
from app.core.case_manager import CaseManager
from app.core.custody_manager import CustodyManager
from app.core.evidence_manager import EvidenceManager
from app.hashing.md5 import md5_file
from app.hashing.sha256 import sha256_file
from app.models import CustodyTransferStatus, CustodyTransferType, UserRole
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
    tests/test_cp_plus_provenance_real_evidence_integration.py."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(evidence_root))
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
def test_custody_lifecycle_against_real_evidence_identity_preserves_source(
    real_evidence_db,
) -> None:
    db, evidence_root = real_evidence_db
    source_path = smallest_real_cpv_path()
    assert source_path is not None

    expected_hashes = load_expected_sha256()
    assert sha256_of(source_path) == expected_hashes[source_path.name]

    case_dir = evidence_root / "CASE-CUSTODY-REAL"
    case_dir.mkdir()
    copied_path = case_dir / source_path.name
    shutil.copy2(source_path, copied_path)

    sha256_before = sha256_file(copied_path)
    md5_before = md5_file(copied_path)
    size_before = copied_path.stat().st_size

    case = CaseManager.create_case(
        db, CaseCreateRequest(case_id="CASE-CUSTODY-REAL", name="Real evidence custody test")
    )
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem,
            source_type="native_export",
            source_path=str(copied_path),
        ),
    )

    # Synthetic custody participants -- standing in for real officers in
    # this automated test, never claiming the real DVR/evidence file
    # itself physically changed hands.
    officer_seizing = AuthManager.create_user(
        db,
        username="real_ev_seizing_officer",
        display_name="Seizing Officer (synthetic)",
        password="password123",
    )
    officer_receiving = AuthManager.create_user(
        db,
        username="real_ev_receiving_officer",
        display_name="Receiving Officer (synthetic)",
        password="password123",
    )
    lab_tech = AuthManager.create_user(
        db,
        username="real_ev_lab_tech",
        display_name="Lab Technician (synthetic)",
        password="password123",
        role=UserRole.LAB_PERSONNEL,
    )

    # Initial intake -- reuses the real Evidence.id, no duplicate identity.
    intake = CustodyManager.record_initial_custody(
        db, evidence_id=evidence.id, receiving_user=officer_seizing
    )
    assert intake.evidence_id == evidence.id
    assert intake.transfer_type == CustodyTransferType.INTAKE

    # Handoff to a second officer, then on to lab personnel -- same
    # mechanism both times.
    issued_1 = CustodyManager.initiate_handoff(
        db,
        evidence_id=evidence.id,
        initiator=officer_seizing,
        receiving_user=officer_receiving,
        location="Field intake",
    )
    CustodyManager.accept_handoff(
        db, raw_token=issued_1.raw_token, accepting_user=officer_receiving
    )

    issued_2 = CustodyManager.initiate_handoff(
        db,
        evidence_id=evidence.id,
        initiator=officer_receiving,
        receiving_user=lab_tech,
        location="Digital forensics lab",
    )
    accepted_2 = CustodyManager.accept_handoff(
        db, raw_token=issued_2.raw_token, accepting_user=lab_tech
    )
    assert accepted_2.status == CustodyTransferStatus.ACCEPTED

    # Current custodian correctly derives from history against the real
    # evidence identity.
    custodian = CustodyManager.get_current_custodian(db, evidence.id)
    assert custodian is not None
    assert custodian.id == lab_tech.id

    history = CustodyManager.get_custody_history(db, evidence.id)
    assert len(history) == 3
    assert all(t.evidence_id == evidence.id for t in history)

    # The custody workflow's own audit chain (Phase 16, reused, not
    # reimplemented) is valid.
    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is True
    assert result.event_count == 3

    # The real evidence file itself is provably untouched by any of the
    # above -- custody state lives entirely in `custody_transfers`/
    # `processing_events`, never in the evidence file.
    assert sha256_file(copied_path) == sha256_before
    assert md5_file(copied_path) == md5_before
    assert copied_path.stat().st_size == size_before
