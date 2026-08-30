"""
Canonical hash-chain-state representation for blockchain anchoring
(Phase 17, Master Specification Section 42 "Blockchain Anchoring").

Pure, DB-free, HTTP-free, provider-free: this module defines exactly
what "the current audit-chain state" means for anchoring purposes, and
how it becomes a single SHA-256 anchor_hash. `app.core.blockchain_manager`
is the DB-aware layer built on top of it; `app.blockchain.provider` is
the infrastructure boundary that submits/retrieves anchors. Neither
computes hashes on its own -- both reuse this module and, transitively,
`app.audit.hash_chain` (Phase 16) and `app.hashing.sha256` (Phase 3).
Nothing here duplicates the Phase 16 hash-chain implementation or the
Phase 3 SHA-256 implementation.

============================================================================
WHY THE CHAIN TIP ALONE IS A SUFFICIENT ANCHOR INPUT
============================================================================
Phase 16's hash chain is already recursive: every event's `current_hash`
folds in its own content plus the previous event's `current_hash`, all
the way back to `GENESIS_PREVIOUS_HASH`. So the *last* event's hash
already cryptographically commits to the exact ordered content of every
event before it -- there is nothing to gain by separately re-hashing the
whole event list a second, different way. Anchoring "the tip" IS
anchoring the full history.

============================================================================
WHY THIS RECOMPUTES FROM RAW EVENT CONTENT, NEVER FROM STORED HASH COLUMNS
============================================================================
`ProcessingEvent.current_hash` is a value some earlier `AuditChainManager.
seal_event` call computed and stored, once, at seal time. Phase 16 never
recomputes it automatically -- a later tamper to an *earlier* event's
content does NOT retroactively change any *later* event's already-stored
`current_hash` column (there is deliberately no silent reseal). If this
module trusted those stored columns, a chain that had been tampered
somewhere in its history could still present an unchanged, stale tip
`current_hash`, and an anchor comparison built on that value would
wrongly report "still matches" even though the true content changed.

`recompute_latest_chain_state` therefore ignores every stored
`previous_hash`/`current_hash` column entirely and re-derives the tip
hash from scratch: it folds `app.audit.hash_chain.compute_event_hash`
over each event's *current* content, in order, from
`GENESIS_PREVIOUS_HASH` forward. The result changes if -- and only if --
the actual ordered event content anchored earlier has actually changed,
regardless of what any stored hash column currently claims. This is the
same reason `AuditChainManager.verify_case_chain` (Phase 16) also never
trusts a stored `current_hash` without recomputing it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from app.audit.hash_chain import (
    CHAIN_ALGORITHM,
    CHAIN_SCOPE,
    GENESIS_PREVIOUS_HASH,
    ChainableEvent,
    compute_event_hash,
)
from app.hashing.sha256 import sha256_bytes

__all__ = [
    "AnchorStatus",
    "AnchorableChainState",
    "EmptyChainStateError",
    "canonicalize_chain_state",
    "compute_anchor_hash",
    "recompute_latest_chain_state",
]


class AnchorStatus(str, Enum):
    """Lifecycle status of one persisted `BlockchainAnchor` row (task
    Phase 17 scope section 12's own suggested vocabulary).

    `LOCAL_TEST` is a distinct terminal status, never `CONFIRMED` --
    `app.blockchain.provider.LocalTestBlockchainProvider` never claims a
    real blockchain transaction occurred (task Phase 17 scope section 7:
    "A test provider must NEVER pretend a real blockchain transaction
    occurred"). `VERIFY_FAILED` (also named in that section) is
    deliberately *not* one of these values -- it describes the outcome
    of *checking* an already-recorded anchor later, not the anchor's own
    creation-time lifecycle, and would otherwise force mutating a
    persisted anchor's status every time someone re-verifies it, which
    breaks the append-oriented/immutability guarantee this table is
    documented to uphold. That outcome instead lives in
    `app.blockchain.verification.AnchorVerificationOutcome`, which is
    never persisted onto the anchor row.
    """

    REQUESTED = "requested"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    LOCAL_TEST = "local_test"


class EmptyChainStateError(ValueError):
    """Raised when asked to anchor a case with zero recorded audit
    events. There is no chain state to anchor -- task Phase 17 scope
    section 3 requires refusing to anchor when no valid state exists."""


@dataclass(frozen=True)
class AnchorableChainState:
    """The exact, deterministic representation of "the current
    audit-chain state" that gets hashed into an anchor.

    Distinct from any single `ProcessingEvent.current_hash` DB column --
    see the module docstring for why this is always freshly recomputed
    from event content rather than read from stored hash columns.
    """

    case_id: int
    chain_scope: str
    chain_algorithm: str
    event_count: int
    first_event_id: int
    last_event_id: int
    latest_chain_hash: str


def recompute_latest_chain_state(
    case_id: int, events: list[ChainableEvent]
) -> AnchorableChainState:
    """Fold a case's events, in the given order, into the current chain state.

    Args:
        case_id: The case these events belong to.
        events: The case's `ProcessingEvent` rows, already converted to
            `ChainableEvent` and already ordered by `id` ascending -- the
            same ordering rule Phase 16 documents and trusts from its
            caller (`app.core.audit_chain_manager`). This function does
            not re-sort; it is the DB-aware caller's responsibility to
            supply the correct order.

    Returns:
        The current `AnchorableChainState`.

    Raises:
        EmptyChainStateError: If `events` is empty -- there is no chain
            state to anchor for a case with no recorded processing history.
    """
    if not events:
        raise EmptyChainStateError(f"case {case_id} has no recorded processing events to anchor")

    previous_hash = GENESIS_PREVIOUS_HASH
    for event in events:
        previous_hash = compute_event_hash(event, previous_hash=previous_hash)

    return AnchorableChainState(
        case_id=case_id,
        chain_scope=CHAIN_SCOPE,
        chain_algorithm=CHAIN_ALGORITHM,
        event_count=len(events),
        first_event_id=events[0].id,
        last_event_id=events[-1].id,
        latest_chain_hash=previous_hash,
    )


def canonicalize_chain_state(state: AnchorableChainState) -> bytes:
    """Produce the exact, deterministic byte sequence hashed into an anchor.

    Same convention as `app.audit.hash_chain.canonicalize_event`: keys in
    alphabetical order (`sort_keys=True`), compact separators, ASCII-only
    escaping, then UTF-8 encoded -- deterministic regardless of how the
    payload dict happens to be constructed.

    Args:
        state: The chain state to canonicalize.

    Returns:
        UTF-8-encoded canonical JSON bytes.
    """
    payload = {
        "case_id": state.case_id,
        "chain_algorithm": state.chain_algorithm,
        "chain_scope": state.chain_scope,
        "event_count": state.event_count,
        "first_event_id": state.first_event_id,
        "last_event_id": state.last_event_id,
        "latest_chain_hash": state.latest_chain_hash,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return text.encode("utf-8")


def compute_anchor_hash(state: AnchorableChainState) -> str:
    """Compute the SHA-256 `anchor_hash` for one chain state.

    Reuses `app.hashing.sha256.sha256_bytes` (Phase 3/16's own SHA-256
    primitive) -- this module never reimplements SHA-256. The result is
    distinct from any individual `ProcessingEvent.current_hash`, any
    artifact hash, and any file hash: it is the fingerprint of the
    *chain state as a whole*, the value actually submitted to an
    external blockchain provider.

    Args:
        state: The chain state to hash.

    Returns:
        The lowercase hex SHA-256 digest of `canonicalize_chain_state(state)`.
    """
    return sha256_bytes(canonicalize_chain_state(state))
