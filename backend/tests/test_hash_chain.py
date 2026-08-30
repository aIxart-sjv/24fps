"""Pure-engine tests for the Phase 16 hash-linked audit chain
(`app.audit.hash_chain`). No database, no HTTP -- these exercise
canonicalization, hashing, and `verify_chain` directly against
hand-built `ChainableEvent`/`ChainLink` objects.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from app.audit.hash_chain import (
    CHAIN_ALGORITHM,
    GENESIS_PREVIOUS_HASH,
    ChainFailureReason,
    ChainLink,
    ChainableEvent,
    canonicalize_event,
    compute_event_hash,
    verify_chain,
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


def _seal(event: ChainableEvent, previous_hash: str) -> ChainLink:
    current_hash = compute_event_hash(event, previous_hash=previous_hash)
    return ChainLink(
        event=event, stored_previous_hash=previous_hash, stored_current_hash=current_hash
    )


def _build_valid_chain(n: int) -> list[ChainLink]:
    links: list[ChainLink] = []
    previous_hash = GENESIS_PREVIOUS_HASH
    for i in range(1, n + 1):
        event = _event(id=i, operation=f"op-{i}")
        link = _seal(event, previous_hash)
        links.append(link)
        previous_hash = link.stored_current_hash  # type: ignore[assignment]
    return links


# ---- Genesis / algorithm constants ----------------------------------------


def test_genesis_previous_hash_is_sha256_of_empty_bytes() -> None:
    import hashlib

    assert GENESIS_PREVIOUS_HASH == hashlib.sha256(b"").hexdigest()


def test_chain_algorithm_is_sha256() -> None:
    assert CHAIN_ALGORITHM == "sha256"


# ---- Canonicalization -------------------------------------------------


def test_canonicalize_event_is_deterministic() -> None:
    event = _event(parameters={"b": 2, "a": 1}, input_artifact_ids=[3, 1, 2])
    assert canonicalize_event(event) == canonicalize_event(event)


def test_canonicalize_event_naive_and_aware_datetimes_match() -> None:
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    naive = aware.replace(tzinfo=None)
    e_aware = _event(started_at=aware)
    e_naive = _event(started_at=naive)
    assert canonicalize_event(e_aware) == canonicalize_event(e_naive)


def test_canonicalize_event_non_utc_aware_datetime_normalizes_to_utc() -> None:
    from datetime import timezone

    aware_utc = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    aware_plus5 = aware_utc.astimezone(timezone(timedelta(hours=5)))
    e1 = _event(started_at=aware_utc)
    e2 = _event(started_at=aware_plus5)
    assert canonicalize_event(e1) == canonicalize_event(e2)


def test_canonicalize_event_none_datetime_is_none() -> None:
    event = _event(started_at=None, completed_at=None)
    assert canonicalize_event(event)  # sanity: does not raise


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation", "extraction"),
        ("actor", "SomeoneElse"),
        ("actor_type", "human"),
        ("tool", "ffmpeg"),
        ("tool_version", "9.9.9"),
        ("software_version", "9.9.9"),
        ("status", "failed"),
        ("error", "boom"),
        ("notes", "different"),
        ("description", "different"),
        ("location_reference", "different"),
        ("case_id", 2),
        ("evidence_id", 5),
        ("job_id", 7),
        ("id", 2),
    ],
)
def test_compute_event_hash_changes_with_every_field(field: str, value: object) -> None:
    base = _event()
    changed = dataclasses.replace(base, **{field: value})
    h1 = compute_event_hash(base, previous_hash=GENESIS_PREVIOUS_HASH)
    h2 = compute_event_hash(changed, previous_hash=GENESIS_PREVIOUS_HASH)
    assert h1 != h2


def test_compute_event_hash_changes_with_parameters() -> None:
    base = _event(parameters={"threshold": 0.5})
    changed = dataclasses.replace(base, parameters={"threshold": 0.9})
    h1 = compute_event_hash(base, previous_hash=GENESIS_PREVIOUS_HASH)
    h2 = compute_event_hash(changed, previous_hash=GENESIS_PREVIOUS_HASH)
    assert h1 != h2


def test_compute_event_hash_changes_with_input_artifact_ids() -> None:
    base = _event(input_artifact_ids=[1, 2])
    changed = dataclasses.replace(base, input_artifact_ids=[1, 2, 3])
    h1 = compute_event_hash(base, previous_hash=GENESIS_PREVIOUS_HASH)
    h2 = compute_event_hash(changed, previous_hash=GENESIS_PREVIOUS_HASH)
    assert h1 != h2


def test_compute_event_hash_changes_with_previous_hash() -> None:
    event = _event()
    h1 = compute_event_hash(event, previous_hash=GENESIS_PREVIOUS_HASH)
    h2 = compute_event_hash(event, previous_hash="a" * 64)
    assert h1 != h2


def test_compute_event_hash_is_reproducible() -> None:
    event = _event()
    h1 = compute_event_hash(event, previous_hash=GENESIS_PREVIOUS_HASH)
    h2 = compute_event_hash(event, previous_hash=GENESIS_PREVIOUS_HASH)
    assert h1 == h2
    assert len(h1) == 64


# ---- verify_chain: valid chains -----------------------------------------


def test_verify_chain_empty_is_valid() -> None:
    result = verify_chain([])
    assert result.valid is True
    assert result.event_count == 0
    assert result.first_event_id is None
    assert result.last_event_id is None
    assert result.failure is None


def test_verify_chain_single_event_valid() -> None:
    links = _build_valid_chain(1)
    result = verify_chain(links)
    assert result.valid is True
    assert result.event_count == 1
    assert result.first_event_id == 1
    assert result.last_event_id == 1


def test_verify_chain_multi_event_valid() -> None:
    links = _build_valid_chain(5)
    result = verify_chain(links)
    assert result.valid is True
    assert result.event_count == 5
    assert result.first_event_id == 1
    assert result.last_event_id == 5


# ---- verify_chain: tamper scenarios --------------------------------------


def test_verify_chain_detects_status_change() -> None:
    links = _build_valid_chain(3)
    tampered_event = dataclasses.replace(links[1].event, status="failed")
    links[1] = dataclasses.replace(links[1], event=tampered_event)
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.event_id == 2
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_verify_chain_detects_parameters_change() -> None:
    links = _build_valid_chain(3)
    tampered_event = dataclasses.replace(links[1].event, parameters={"tampered": True})
    links[1] = dataclasses.replace(links[1], event=tampered_event)
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.event_id == 2
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_verify_chain_detects_tool_version_change() -> None:
    links = _build_valid_chain(3)
    tampered_event = dataclasses.replace(links[1].event, tool_version="9.9.9")
    links[1] = dataclasses.replace(links[1], event=tampered_event)
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_verify_chain_detects_input_artifact_ids_change() -> None:
    links = _build_valid_chain(3)
    tampered_event = dataclasses.replace(links[1].event, input_artifact_ids=[999])
    links[1] = dataclasses.replace(links[1], event=tampered_event)
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_verify_chain_detects_previous_hash_tamper() -> None:
    links = _build_valid_chain(3)
    links[2] = dataclasses.replace(links[2], stored_previous_hash="b" * 64)
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.event_id == 3
    assert result.failure.reason == ChainFailureReason.BROKEN_LINK


def test_verify_chain_detects_current_hash_tamper() -> None:
    links = _build_valid_chain(3)
    links[1] = dataclasses.replace(links[1], stored_current_hash="c" * 64)
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.event_id == 2
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_verify_chain_detects_deleted_middle_event() -> None:
    links = _build_valid_chain(3)
    del links[1]  # simulate deletion: only events 1 and 3 remain
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.event_id == 3
    assert result.failure.reason == ChainFailureReason.BROKEN_LINK


def test_verify_chain_detects_out_of_order_insertion() -> None:
    links = _build_valid_chain(3)
    links[0], links[1] = links[1], links[0]  # swap: no longer in id/hash order
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    # The swapped first link's stored_previous_hash no longer matches genesis.
    assert result.failure.reason == ChainFailureReason.INVALID_GENESIS


def test_verify_chain_detects_predecessor_modification_via_broken_link() -> None:
    links = _build_valid_chain(3)
    # Modify event 1's content without recomputing its own or event 2's hash --
    # event 1 itself now fails CURRENT_HASH_MISMATCH first (it is walked before 2).
    tampered_event = dataclasses.replace(links[0].event, status="failed")
    links[0] = dataclasses.replace(links[0], event=tampered_event)
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.event_id == 1
    assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH


def test_verify_chain_predecessor_modified_but_own_hash_resealed_breaks_next_link() -> None:
    """A middle event must still validate its predecessor relationship --
    it must not be reported valid merely because its own current_hash
    matches, if the link to its (altered) predecessor is broken."""
    links = _build_valid_chain(3)
    tampered_event = dataclasses.replace(links[0].event, status="failed")
    new_hash = compute_event_hash(tampered_event, previous_hash=GENESIS_PREVIOUS_HASH)
    links[0] = ChainLink(
        event=tampered_event,
        stored_previous_hash=GENESIS_PREVIOUS_HASH,
        stored_current_hash=new_hash,
    )
    # Event 2 still points at the *original* (pre-tamper) hash of event 1.
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.event_id == 2
    assert result.failure.reason == ChainFailureReason.BROKEN_LINK


def test_verify_chain_detects_missing_hash() -> None:
    links = _build_valid_chain(2)
    links[1] = dataclasses.replace(links[1], stored_current_hash=None)
    result = verify_chain(links)
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.event_id == 2
    assert result.failure.reason == ChainFailureReason.MISSING_HASH


def test_verify_chain_detects_invalid_genesis() -> None:
    event = _event(id=1)
    link = _seal(event, previous_hash="d" * 64)  # not GENESIS_PREVIOUS_HASH
    result = verify_chain([link])
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.event_id == 1
    assert result.failure.reason == ChainFailureReason.INVALID_GENESIS


# ---- verify_chain: expected_event_ids -----------------------------------


def test_verify_chain_expected_event_ids_missing_event() -> None:
    links = _build_valid_chain(2)
    result = verify_chain(links, expected_event_ids=[1, 2, 3])
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.reason == ChainFailureReason.MISSING_EVENT
    assert result.failure.event_id == 3


def test_verify_chain_expected_event_ids_unexpected_event() -> None:
    links = _build_valid_chain(3)
    result = verify_chain(links, expected_event_ids=[1, 2])
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.reason == ChainFailureReason.UNEXPECTED_EVENT
    assert result.failure.event_id == 3


def test_verify_chain_expected_event_ids_reordered() -> None:
    links = _build_valid_chain(3)
    result = verify_chain(links, expected_event_ids=[1, 3, 2])
    assert result.valid is False
    assert result.failure is not None
    assert result.failure.reason == ChainFailureReason.REORDERED_EVENT


def test_verify_chain_expected_event_ids_matching_is_valid() -> None:
    links = _build_valid_chain(3)
    result = verify_chain(links, expected_event_ids=[1, 2, 3])
    assert result.valid is True
