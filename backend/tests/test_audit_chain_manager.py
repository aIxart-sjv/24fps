"""DB-level tests for app/core/audit_chain_manager.py (Phase 16).

Events are only ever created through `ProvenanceManager.record_event`
(the sole entry point) so these tests exercise sealing end-to-end and
then verify tampering scenarios by mutating persisted rows directly,
bypassing the API surface entirely -- exactly the kind of tampering the
chain exists to detect.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit import ActorType, ProcessingOperation
from app.audit.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    ChainFailureReason,
    compute_event_hash,
)
from app.core.audit_chain_manager import AuditChainManager, _to_chainable
from app.core.case_manager import CaseManager
from app.core.provenance_manager import ProvenanceManager
from app.models import Case, JobStatus, ProcessingEvent
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _make_case(db, case_id: str = "CASE-CHAIN-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Chain test"))


def _record(db, case: Case, operation: str, **kwargs: object) -> ProcessingEvent:
    return ProvenanceManager.record_event(
        db,
        case_id=case.id,
        operation=operation,
        actor=kwargs.pop("actor", "TestActor"),  # type: ignore[arg-type]
        actor_type=kwargs.pop("actor_type", ActorType.SYSTEM),  # type: ignore[arg-type]
        status=kwargs.pop("status", JobStatus.COMPLETED),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


# ---- seal_event -----------------------------------------------------------


def test_record_event_always_seals_hashes(db) -> None:
    case = _make_case(db)
    event = _record(db, case, ProcessingOperation.PARSING.value)
    assert event.previous_hash is not None
    assert event.current_hash is not None
    assert len(event.current_hash) == 64


def test_first_event_previous_hash_is_genesis(db) -> None:
    case = _make_case(db)
    event = _record(db, case, ProcessingOperation.PARSING.value)
    assert event.previous_hash == GENESIS_PREVIOUS_HASH


def test_second_event_previous_hash_is_first_events_current_hash(db) -> None:
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value)
    e2 = _record(db, case, ProcessingOperation.EXTRACTION.value)
    assert e2.previous_hash == e1.current_hash


def test_current_hash_is_reproducible_externally(db) -> None:
    case = _make_case(db)
    event = _record(db, case, ProcessingOperation.PARSING.value)
    assert event.previous_hash is not None
    recomputed = compute_event_hash(_to_chainable(event), previous_hash=event.previous_hash)
    assert recomputed == event.current_hash


def test_seal_event_does_not_rewrite_prior_history(db) -> None:
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value)
    hash_before = e1.current_hash
    _record(db, case, ProcessingOperation.EXTRACTION.value)
    reloaded = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    assert reloaded.current_hash == hash_before


def test_independent_case_chains_never_cross_link(db) -> None:
    case_a = _make_case(db, "CASE-CHAIN-A")
    case_b = _make_case(db, "CASE-CHAIN-B")
    ea = _record(db, case_a, ProcessingOperation.PARSING.value)
    eb = _record(db, case_b, ProcessingOperation.PARSING.value)
    assert ea.previous_hash == GENESIS_PREVIOUS_HASH
    assert eb.previous_hash == GENESIS_PREVIOUS_HASH
    assert ea.current_hash != eb.current_hash


# ---- verify_case_chain: valid --------------------------------------------


def test_verify_case_chain_valid_multi_event(db) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    _record(db, case, ProcessingOperation.EXTRACTION.value)
    _record(db, case, ProcessingOperation.VALIDATION.value)

    result = AuditChainManager.verify_case_chain(db, case.id)

    assert result.valid is True
    assert result.event_count == 3
    assert result.case_id == case.id
    assert result.chain_scope == "case"
    assert result.failure is None


def test_verify_case_chain_empty_is_valid(db) -> None:
    case = _make_case(db)
    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is True
    assert result.event_count == 0
    assert result.case_id == case.id


def test_verify_case_chain_nonexistent_case_is_trivially_valid_empty(db) -> None:
    result = AuditChainManager.verify_case_chain(db, 999999)
    assert result.valid is True
    assert result.event_count == 0


# ---- verify_case_chain: tamper scenarios (direct row mutation) ----------


def test_detects_status_change(db) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    e2 = _record(db, case, ProcessingOperation.EXTRACTION.value)

    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e2.id).first()
    row.status = "failed"
    db.commit()

    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is False
    assert result.failure.event_id == e2.id
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_detects_parameters_change(db) -> None:
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value, parameters={"a": 1})

    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    import json

    row.parameters = json.dumps({"a": 2})
    db.commit()

    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is False
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_detects_tool_version_change(db) -> None:
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value, tool="ffmpeg", tool_version="1.0")

    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    row.tool_version = "2.0"
    db.commit()

    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is False
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_detects_input_artifact_ids_change(db) -> None:
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value)

    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    import json

    row.input_artifact_ids = json.dumps([123])
    db.commit()

    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is False
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_detects_previous_hash_change(db) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    e2 = _record(db, case, ProcessingOperation.EXTRACTION.value)

    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e2.id).first()
    row.previous_hash = "f" * 64
    db.commit()

    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is False
    assert result.failure.event_id == e2.id
    assert result.failure.reason == ChainFailureReason.BROKEN_LINK


def test_detects_current_hash_change(db) -> None:
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value)

    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    row.current_hash = "e" * 64
    db.commit()

    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is False
    assert result.failure.event_id == e1.id
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_detects_deleted_event(db) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    e2 = _record(db, case, ProcessingOperation.EXTRACTION.value)
    _record(db, case, ProcessingOperation.VALIDATION.value)

    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e2.id).first()
    db.delete(row)
    db.commit()

    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is False
    assert result.failure.reason == ChainFailureReason.BROKEN_LINK


def test_detects_predecessor_modification(db) -> None:
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value)
    _record(db, case, ProcessingOperation.EXTRACTION.value)

    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    row.notes = "tampered predecessor"
    db.commit()

    result = AuditChainManager.verify_case_chain(db, case.id)
    assert result.valid is False
    # Event 1 itself fails first (its own recomputed hash no longer matches).
    assert result.failure.event_id == e1.id
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_verify_does_not_silently_repair(db) -> None:
    """No rebuild/reseal: verifying a tampered chain never mutates stored rows."""
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value)
    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    row.status = "failed"
    db.commit()
    tampered_current_hash = row.current_hash

    AuditChainManager.verify_case_chain(db, case.id)

    reloaded = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    assert reloaded.current_hash == tampered_current_hash
    assert reloaded.status == "failed"


# ---- recompute_event_hash --------------------------------------------


def test_recompute_event_hash_matches_stored_value_when_untampered(db) -> None:
    case = _make_case(db)
    event = _record(db, case, ProcessingOperation.PARSING.value)
    assert AuditChainManager.recompute_event_hash(db, event.id) == event.current_hash


def test_recompute_event_hash_missing_event_raises(db) -> None:
    with pytest.raises(ValueError):
        AuditChainManager.recompute_event_hash(db, 999999)
