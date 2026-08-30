"""Pure-engine tests for the Phase 17 anchor-state representation
(`app.blockchain.anchor`). No database, no HTTP, no provider -- these
exercise canonicalization, chain-state folding, and anchor hashing
directly against hand-built `ChainableEvent` objects.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.audit.hash_chain import GENESIS_PREVIOUS_HASH, ChainableEvent, compute_event_hash
from app.blockchain.anchor import (
    CHAIN_ALGORITHM,
    CHAIN_SCOPE,
    AnchorableChainState,
    EmptyChainStateError,
    canonicalize_chain_state,
    compute_anchor_hash,
    recompute_latest_chain_state,
)


def _event(**overrides: object) -> ChainableEvent:
    base: dict[str, object] = dict(
        id=1,
        case_id=1,
        evidence_id=None,
        job_id=None,
        operation="parsing",
        actor="CPPlusParser",
        actor_type="system",
        tool="CPPlusParser",
        tool_version="0.2.0",
        software_version="0.1.0",
        parameters=None,
        input_artifact_ids=None,
        output_artifact_ids=None,
        started_at=None,
        completed_at=None,
        status="completed",
        warnings=None,
        error=None,
        notes=None,
        description=None,
        location_reference=None,
    )
    base.update(overrides)
    return ChainableEvent(**base)  # type: ignore[arg-type]


def _events(n: int) -> list[ChainableEvent]:
    return [_event(id=i, operation=f"op-{i}") for i in range(1, n + 1)]


# ---- recompute_latest_chain_state ----------------------------------------


def test_recompute_empty_events_raises() -> None:
    with pytest.raises(EmptyChainStateError):
        recompute_latest_chain_state(1, [])


def test_recompute_single_event_matches_manual_fold() -> None:
    events = _events(1)
    state = recompute_latest_chain_state(1, events)
    expected_tip = compute_event_hash(events[0], previous_hash=GENESIS_PREVIOUS_HASH)
    assert state.latest_chain_hash == expected_tip
    assert state.event_count == 1
    assert state.first_event_id == 1
    assert state.last_event_id == 1
    assert state.case_id == 1
    assert state.chain_scope == CHAIN_SCOPE
    assert state.chain_algorithm == CHAIN_ALGORITHM


def test_recompute_multi_event_matches_manual_fold() -> None:
    events = _events(4)
    state = recompute_latest_chain_state(7, events)

    previous_hash = GENESIS_PREVIOUS_HASH
    for event in events:
        previous_hash = compute_event_hash(event, previous_hash=previous_hash)

    assert state.latest_chain_hash == previous_hash
    assert state.event_count == 4
    assert state.first_event_id == 1
    assert state.last_event_id == 4
    assert state.case_id == 7


def test_recompute_ignores_stored_hash_columns_entirely() -> None:
    """`recompute_latest_chain_state` only ever looks at ChainableEvent
    content -- there is no stored-hash concept here at all, unlike
    Phase 16's `verify_chain`. Two independently-built event lists with
    identical content produce identical chain state regardless of any
    notion of "what was previously stored"."""
    events_a = _events(3)
    events_b = [dataclasses.replace(e) for e in _events(3)]
    state_a = recompute_latest_chain_state(1, events_a)
    state_b = recompute_latest_chain_state(1, events_b)
    assert state_a.latest_chain_hash == state_b.latest_chain_hash


def test_recompute_is_sensitive_to_content_change() -> None:
    events = _events(3)
    state_before = recompute_latest_chain_state(1, events)

    tampered = list(events)
    tampered[1] = dataclasses.replace(tampered[1], status="failed")
    state_after = recompute_latest_chain_state(1, tampered)

    assert state_before.latest_chain_hash != state_after.latest_chain_hash


def test_recompute_is_sensitive_to_ordering() -> None:
    events = _events(3)
    state_forward = recompute_latest_chain_state(1, events)
    state_swapped = recompute_latest_chain_state(1, [events[1], events[0], events[2]])
    assert state_forward.latest_chain_hash != state_swapped.latest_chain_hash


def test_recompute_is_sensitive_to_event_count() -> None:
    state_2 = recompute_latest_chain_state(1, _events(2))
    state_3 = recompute_latest_chain_state(1, _events(3))
    assert state_2.latest_chain_hash != state_3.latest_chain_hash


# ---- canonicalize_chain_state / compute_anchor_hash -----------------------


def test_canonicalize_chain_state_is_deterministic() -> None:
    state = AnchorableChainState(
        case_id=1,
        chain_scope=CHAIN_SCOPE,
        chain_algorithm=CHAIN_ALGORITHM,
        event_count=2,
        first_event_id=1,
        last_event_id=2,
        latest_chain_hash="a" * 64,
    )
    assert canonicalize_chain_state(state) == canonicalize_chain_state(state)


def test_same_chain_produces_same_anchor_hash() -> None:
    events = _events(3)
    state1 = recompute_latest_chain_state(1, events)
    state2 = recompute_latest_chain_state(1, list(events))
    assert compute_anchor_hash(state1) == compute_anchor_hash(state2)


def test_changed_chain_produces_different_anchor_hash() -> None:
    events = _events(3)
    state_before = recompute_latest_chain_state(1, events)

    tampered = list(events)
    tampered[0] = dataclasses.replace(tampered[0], actor="SomeoneElse")
    state_after = recompute_latest_chain_state(1, tampered)

    assert compute_anchor_hash(state_before) != compute_anchor_hash(state_after)


@pytest.mark.parametrize(
    "field,value",
    [
        ("case_id", 2),
        ("chain_scope", "evidence"),
        ("chain_algorithm", "sha1"),
        ("event_count", 99),
        ("first_event_id", 99),
        ("last_event_id", 99),
        ("latest_chain_hash", "b" * 64),
    ],
)
def test_compute_anchor_hash_changes_with_every_field(field: str, value: object) -> None:
    base = AnchorableChainState(
        case_id=1,
        chain_scope=CHAIN_SCOPE,
        chain_algorithm=CHAIN_ALGORITHM,
        event_count=2,
        first_event_id=1,
        last_event_id=2,
        latest_chain_hash="a" * 64,
    )
    changed = dataclasses.replace(base, **{field: value})
    assert compute_anchor_hash(base) != compute_anchor_hash(changed)


def test_compute_anchor_hash_is_reproducible() -> None:
    state = recompute_latest_chain_state(1, _events(2))
    assert compute_anchor_hash(state) == compute_anchor_hash(state)
    assert len(compute_anchor_hash(state)) == 64
