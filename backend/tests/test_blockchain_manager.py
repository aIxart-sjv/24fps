"""DB-level tests for app/core/blockchain_manager.py (Phase 17).

Every anchor is created through `BlockchainManager.create_anchor` (the
sole entry point) against a real Phase 15/16 `ProvenanceManager`-recorded
audit chain, using an explicit `LocalTestBlockchainProvider()` instance
per test for isolation (never the shared config-driven singleton).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit import ActorType, ProcessingOperation
from app.blockchain.anchor import AnchorStatus
from app.blockchain.provider import AnchorSubmissionError, LocalTestBlockchainProvider
from app.blockchain.verification import AnchorVerificationOutcome
from app.core.blockchain_manager import BlockchainManager, ChainNotValidForAnchoringError
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


@pytest.fixture
def provider() -> LocalTestBlockchainProvider:
    return LocalTestBlockchainProvider()


def _make_case(db, case_id: str = "CASE-CHAIN-ANCHOR-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Anchor test"))


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


# ---- create_anchor: preconditions -----------------------------------------


def test_create_anchor_missing_case_raises(db, provider) -> None:
    with pytest.raises(ValueError):
        BlockchainManager.create_anchor(db, case_id=999999, provider=provider)


def test_create_anchor_empty_chain_raises(db, provider) -> None:
    case = _make_case(db)
    with pytest.raises(ChainNotValidForAnchoringError):
        BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)
    # No anchor and no processing event were written.
    assert BlockchainManager.list_anchors(db, case.id) == []
    assert ProvenanceManager.get_case_history(db, case.id) == []


def test_create_anchor_tampered_chain_raises_and_writes_nothing(db, provider) -> None:
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value)
    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    row.status = "failed"
    db.commit()

    with pytest.raises(ChainNotValidForAnchoringError):
        BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)

    assert BlockchainManager.list_anchors(db, case.id) == []


# ---- create_anchor: happy path (task Phase 17 scope section 28) -----------


def test_create_anchor_on_valid_chain_succeeds(db, provider) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    _record(db, case, ProcessingOperation.EXTRACTION.value)

    anchor = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)

    assert anchor.case_id == case.id
    assert anchor.chain_id == f"case-{case.id}"
    assert anchor.provider == "local_testnet"
    assert anchor.status == AnchorStatus.LOCAL_TEST.value
    assert anchor.transaction_reference.startswith("LOCAL-TEST-ANCHOR-")
    assert len(anchor.audit_state_hash) == 64
    assert anchor.verified_at is None


def test_create_anchor_records_a_processing_event(db, provider) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)

    history = ProvenanceManager.get_case_history(db, case.id)
    anchor_events = [
        e for e in history if e.operation == ProcessingOperation.BLOCKCHAIN_ANCHOR.value
    ]
    assert len(anchor_events) == 1
    assert anchor_events[0].status == "completed"


def test_create_anchor_event_extends_but_does_not_alter_anchored_state(db, provider) -> None:
    """The ProcessingEvent recorded for the anchoring action itself is
    a *new* chain entry -- it must never be part of what the anchor
    hash represents (task Phase 17 scope section 24)."""
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)

    from app.blockchain.anchor import compute_anchor_hash, recompute_latest_chain_state
    from app.core.audit_chain_manager import _to_chainable

    events_before = (
        db.query(ProcessingEvent)
        .filter(ProcessingEvent.case_id == case.id)
        .order_by(ProcessingEvent.id.asc())
        .all()
    )
    expected_hash = compute_anchor_hash(
        recompute_latest_chain_state(case.id, [_to_chainable(e) for e in events_before])
    )

    anchor = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)

    assert anchor.audit_state_hash == expected_hash
    # A new event now exists (the anchoring action itself).
    events_after = db.query(ProcessingEvent).filter(ProcessingEvent.case_id == case.id).count()
    assert events_after == len(events_before) + 1


def test_create_anchor_with_reason(db, provider) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    anchor = BlockchainManager.create_anchor(
        db, case_id=case.id, provider=provider, reason="periodic"
    )
    assert anchor.reason == "periodic"


# ---- multiple anchors (task Phase 17 scope section 30) --------------------


def test_multiple_anchors_are_all_retained(db, provider) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    anchor1 = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider, reason="a1")

    _record(db, case, ProcessingOperation.EXTRACTION.value)
    anchor2 = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider, reason="a2")

    _record(db, case, ProcessingOperation.VALIDATION.value)
    anchor3 = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider, reason="a3")

    anchors = BlockchainManager.list_anchors(db, case.id)
    assert [a.id for a in anchors] == [anchor1.id, anchor2.id, anchor3.id]
    assert len({a.transaction_reference for a in anchors}) == 3
    assert len({a.audit_state_hash for a in anchors}) == 3

    # Earlier anchors are never mutated by later ones.
    reloaded1 = BlockchainManager.get_anchor(db, anchor1.id)
    assert reloaded1.audit_state_hash == anchor1.audit_state_hash
    assert reloaded1.transaction_reference == anchor1.transaction_reference

    # The latest anchor is determinable (highest id / last in list).
    assert anchors[-1].id == anchor3.id


def test_list_anchors_empty_for_case_with_none(db) -> None:
    case = _make_case(db)
    assert BlockchainManager.list_anchors(db, case.id) == []


# ---- verify_anchor: valid ---------------------------------------------


def test_verify_anchor_valid_chain(db, provider) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    anchor = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)

    result = BlockchainManager.verify_anchor(db, anchor_id=anchor.id, provider=provider)

    assert result.valid is True
    assert result.outcome == AnchorVerificationOutcome.VALID
    assert result.expected_hash == anchor.audit_state_hash
    assert result.anchored_hash == anchor.audit_state_hash

    reloaded = BlockchainManager.get_anchor(db, anchor.id)
    assert reloaded.verified_at is not None


def test_verify_anchor_missing_id_raises(db) -> None:
    with pytest.raises(ValueError):
        BlockchainManager.verify_anchor(db, anchor_id=999999)


# ---- local chain change after anchor (task Phase 17 scope section 14/29) --


def test_local_chain_tamper_after_anchor_is_detected(db, provider) -> None:
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value)
    anchor = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)

    valid_result = BlockchainManager.verify_anchor(db, anchor_id=anchor.id, provider=provider)
    assert valid_result.valid is True

    # Tamper the local audit history after anchoring.
    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    row.status = "failed"
    db.commit()

    # Phase 16 chain now fails on its own terms.
    from app.core.audit_chain_manager import AuditChainManager

    chain_check = AuditChainManager.verify_case_chain(db, case.id)
    assert chain_check.valid is False

    tampered_result = BlockchainManager.verify_anchor(db, anchor_id=anchor.id, provider=provider)
    assert tampered_result.valid is False
    assert tampered_result.outcome == AnchorVerificationOutcome.CHAIN_INVALID
    assert tampered_result.chain_valid is False

    # The blockchain anchor itself was never silently rewritten.
    reloaded = BlockchainManager.get_anchor(db, anchor.id)
    assert reloaded.audit_state_hash == anchor.audit_state_hash
    assert reloaded.transaction_reference == anchor.transaction_reference
    assert reloaded.status == anchor.status


def test_legitimate_chain_growth_after_anchor_does_not_invalidate_it(db, provider) -> None:
    """An anchor commits to "the chain through event `last_event_id`".
    Adding further, validly-sealed events afterward (Phase 16 chain
    still verifies) is normal growth, not tampering -- an earlier
    checkpoint must not retroactively read as broken just because more
    history has legitimately accumulated since."""
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    anchor = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)

    # Growing the chain further (a legitimate new operation, plus the
    # anchoring action's own recorded ProcessingEvent).
    _record(db, case, ProcessingOperation.EXTRACTION.value)

    result = BlockchainManager.verify_anchor(db, anchor_id=anchor.id, provider=provider)
    assert result.chain_valid is True
    assert result.valid is True
    assert result.outcome == AnchorVerificationOutcome.VALID
    assert result.expected_hash == result.anchored_hash


def test_tampering_within_the_anchored_prefix_is_detected_after_growth(db, provider) -> None:
    """Even after the chain has legitimately grown past an anchor,
    tampering an event that *was* part of the anchored prefix is still
    caught (via the overall Phase 16 chain no longer verifying)."""
    case = _make_case(db)
    e1 = _record(db, case, ProcessingOperation.PARSING.value)
    anchor = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)
    _record(db, case, ProcessingOperation.EXTRACTION.value)

    row = db.query(ProcessingEvent).filter(ProcessingEvent.id == e1.id).first()
    row.status = "failed"
    db.commit()

    result = BlockchainManager.verify_anchor(db, anchor_id=anchor.id, provider=provider)
    assert result.valid is False
    assert result.outcome == AnchorVerificationOutcome.CHAIN_INVALID
    assert result.chain_valid is False


# ---- provider failure handling (task Phase 17 scope section 31) -----------


class _FailingProvider(LocalTestBlockchainProvider):
    def create_anchor(self, anchor_hash, metadata):  # type: ignore[override]
        raise AnchorSubmissionError("simulated provider rejection")


def test_create_anchor_provider_failure_is_controlled_and_logged(db) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    failing_provider = _FailingProvider()

    with pytest.raises(AnchorSubmissionError):
        BlockchainManager.create_anchor(db, case_id=case.id, provider=failing_provider)

    # No anchor row was persisted.
    assert BlockchainManager.list_anchors(db, case.id) == []

    # But the failed attempt is recorded in provenance history.
    history = ProvenanceManager.get_case_history(db, case.id)
    anchor_events = [
        e for e in history if e.operation == ProcessingOperation.BLOCKCHAIN_ANCHOR.value
    ]
    assert len(anchor_events) == 1
    assert anchor_events[0].status == "failed"
    assert anchor_events[0].error is not None


def test_verify_anchor_provider_not_found_transaction(db, provider) -> None:
    case = _make_case(db)
    _record(db, case, ProcessingOperation.PARSING.value)
    anchor = BlockchainManager.create_anchor(db, case_id=case.id, provider=provider)

    # Verify against a *different*, empty provider instance -- simulates
    # the provider having no record of this transaction.
    other_provider = LocalTestBlockchainProvider()
    result = BlockchainManager.verify_anchor(db, anchor_id=anchor.id, provider=other_provider)

    assert result.valid is False
    assert result.outcome == AnchorVerificationOutcome.ANCHOR_NOT_FOUND
    assert result.anchored_hash is None
