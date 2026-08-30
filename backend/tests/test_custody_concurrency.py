"""Concurrency tests for app/core/custody_manager.py (Phase 21, Part A).

Task Phase 21 scope: "handle concurrent/pending transfers so two
transfers can't silently take ownership from the same custodian" and
"use transactional locking or equivalent" for accept/cancel races. These
tests use real OS threads against a real, file-based SQLite database
(not `:memory:` with a single shared connection) so the two races below
are genuine, not simulated:

1. Two threads racing to `initiate_handoff` for the same evidence item
   at (as close as possible to) the same instant -- exactly one may
   create a PENDING transfer; the DB-level partial unique index
   (`app.models.custody.CustodyTransfer.__table_args__`) is the actual
   guarantee, not application-level locking.
2. Two threads racing to `accept_handoff` on the *same* token -- exactly
   one may succeed; the atomic conditional UPDATE
   (`CustodyManager._atomic_transition`) is the actual guarantee.
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth_manager import AuthManager
from app.core.case_manager import CaseManager
from app.core.custody_manager import CustodyManager
from app.core.evidence_manager import EvidenceManager
from app.models import CustodyTransfer, CustodyTransferStatus, CustodyTransferType
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base


@pytest.fixture
def file_db_sessionmaker():
    """A real file-based SQLite database so concurrent threads use
    genuinely separate connections (unlike a single shared `:memory:`
    connection, which would serialize everything trivially and prove
    nothing about the actual race-safety mechanisms)."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "custody_race_test.db"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        yield session_factory
        engine.dispose()


def _bootstrap(session_factory):
    db = session_factory()
    try:
        case = CaseManager.create_case(
            db, CaseCreateRequest(case_id="CASE-RACE-1", name="Race test case")
        )
        evidence = EvidenceManager.register_evidence(
            db,
            case_id=case.id,
            request=EvidenceCreateRequest(
                evidence_id="CASE-RACE-1-EV-1", source_type="disk_image", source_description="d"
            ),
        )
        officer_a = AuthManager.create_user(
            db, username="race_a", display_name="Race A", password="password123"
        )
        officer_b = AuthManager.create_user(
            db, username="race_b", display_name="Race B", password="password123"
        )
        officer_c = AuthManager.create_user(
            db, username="race_c", display_name="Race C", password="password123"
        )
        CustodyManager.record_initial_custody(db, evidence_id=evidence.id, receiving_user=officer_a)
        return evidence.id, officer_a.id, officer_b.id, officer_c.id
    finally:
        db.close()


class TestConcurrentInitiate:
    def test_only_one_concurrent_initiate_wins(self, file_db_sessionmaker) -> None:
        evidence_id, officer_a_id, officer_b_id, officer_c_id = _bootstrap(file_db_sessionmaker)

        results: list[str] = []
        barrier = threading.Barrier(2)

        def worker(receiving_user_id: int) -> None:
            db = file_db_sessionmaker()
            try:
                from app.models import User

                initiator = db.query(User).filter(User.id == officer_a_id).first()
                receiver = db.query(User).filter(User.id == receiving_user_id).first()
                barrier.wait(timeout=5)
                try:
                    CustodyManager.initiate_handoff(
                        db,
                        evidence_id=evidence_id,
                        initiator=initiator,
                        receiving_user=receiver,
                    )
                    results.append("success")
                except ValueError:
                    results.append("rejected")
            finally:
                db.close()

        t1 = threading.Thread(target=worker, args=(officer_b_id,))
        t2 = threading.Thread(target=worker, args=(officer_c_id,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert results.count("success") == 1, results
        assert results.count("rejected") == 1, results

        # Exactly one PENDING transfer exists for this evidence item.
        verify_db = file_db_sessionmaker()
        try:
            pending = (
                verify_db.query(CustodyTransfer)
                .filter(
                    CustodyTransfer.evidence_id == evidence_id,
                    CustodyTransfer.status == CustodyTransferStatus.PENDING,
                )
                .all()
            )
            assert len(pending) == 1
        finally:
            verify_db.close()


class TestConcurrentAccept:
    def test_only_one_concurrent_accept_wins(self, file_db_sessionmaker) -> None:
        evidence_id, officer_a_id, officer_b_id, officer_c_id = _bootstrap(file_db_sessionmaker)

        setup_db = file_db_sessionmaker()
        try:
            from app.models import User

            initiator = setup_db.query(User).filter(User.id == officer_a_id).first()
            receiver = setup_db.query(User).filter(User.id == officer_b_id).first()
            issued = CustodyManager.initiate_handoff(
                setup_db, evidence_id=evidence_id, initiator=initiator, receiving_user=receiver
            )
            raw_token = issued.raw_token
        finally:
            setup_db.close()

        results: list[str] = []
        barrier = threading.Barrier(2)

        def worker() -> None:
            db = file_db_sessionmaker()
            try:
                from app.models import User

                accepting_user = db.query(User).filter(User.id == officer_b_id).first()
                barrier.wait(timeout=5)
                try:
                    CustodyManager.accept_handoff(
                        db, raw_token=raw_token, accepting_user=accepting_user
                    )
                    results.append("success")
                except ValueError:
                    results.append("rejected")
            finally:
                db.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert results.count("success") == 1, results
        assert results.count("rejected") == 1, results

        verify_db = file_db_sessionmaker()
        try:
            accepted_transfers = (
                verify_db.query(CustodyTransfer)
                .filter(CustodyTransfer.evidence_id == evidence_id)
                .filter(CustodyTransfer.transfer_type == CustodyTransferType.TRANSFER)
                .filter(CustodyTransfer.status == CustodyTransferStatus.ACCEPTED)
                .all()
            )
            assert len(accepted_transfers) == 1
        finally:
            verify_db.close()
