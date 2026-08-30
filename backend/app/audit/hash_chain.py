"""
Hash-linked audit chain -- canonical serialization and verification
(Phase 16, Master Specification Section 41 "Hash-Linked Audit Log").

Pure, DB-free, HTTP-free: this module defines exactly what belongs in the
hash of one `ProcessingEvent` (Phase 15) and how two events chain
together. `app.core.audit_chain_manager.AuditChainManager` is the
DB-aware layer built on top of it, mirroring every prior phase's
pure-engine/DB-manager split (Phase 9-15).

Formula (Master Specification Section 41, verbatim):
    current_hash = SHA-256(canonicalized_event_data + previous_record_hash)

Reuses `app.hashing.sha256.sha256_bytes` (Phase 3's own SHA-256 primitive,
extended in Phase 16 with an in-memory-bytes variant alongside its
existing file-hashing one) -- this module never reimplements SHA-256.

A bare hash chain is tamper-*evident* against accidental or naive
corruption -- it is not, by itself, cryptographically secure against a
sophisticated attacker with full database write access who recomputes
the entire downstream chain after tampering (SHA-256 here uses no secret
key). NTRO requirements Section 23 makes the same point and explicitly
defers a stronger mechanism (digital signatures / an external anchor) to
later work -- Phase 17 in this project. Phase 16 does not attempt to
solve that; it makes ordinary tampering (an edited field, a deleted
event, an out-of-order insertion) detectable and precisely diagnosable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.hashing.sha256 import sha256_bytes

__all__ = [
    "CHAIN_ALGORITHM",
    "CHAIN_SCOPE",
    "GENESIS_PREVIOUS_HASH",
    "ChainFailure",
    "ChainFailureReason",
    "ChainLink",
    "ChainVerificationResult",
    "ChainableEvent",
    "canonicalize_event",
    "compute_event_hash",
    "verify_chain",
]

#: Master Specification Section 41's documented algorithm -- never
#: silently substituted for another one.
CHAIN_ALGORITHM = "sha256"

#: One chain per case (Phase 15's `ProcessingEvent.case_id` is the only
#: non-nullable scoping field on every event, making case-level scope the
#: unambiguous natural boundary -- documented explicitly per the task's
#: own instruction not to assume this silently).
CHAIN_SCOPE = "case"

#: The first event in a chain has no predecessor. Rather than a random or
#: project-invented sentinel, this is a fixed, universally-reproducible
#: constant: the SHA-256 hash of the empty byte string. Any independent
#: implementation of this same scheme derives the identical value.
GENESIS_PREVIOUS_HASH = sha256_bytes(b"")


@dataclass(frozen=True)
class ChainableEvent:
    """The exact set of `ProcessingEvent` fields that participate in the
    audit hash -- decoupled from the ORM row so canonicalization is
    testable without a database.

    Included: every field semantically part of "what happened" (task
    Phase 16 scope: "Include semantically important processing
    content"), plus:
    - `id`: each event's own stable identity. Without it, two events
      with byte-identical content (e.g. two "extraction completed, no
      warnings" events) would hash identically, colliding two genuinely
      distinct chain entries.
    - `operation`: the single most semantically important fact about the
      event. The task's own candidate field list omits it; that
      omission is treated as an oversight here -- excluding it would
      make a tampered `operation` value undetectable, directly
      contradicting the task's own "detect changed event content"
      requirement.

    Excluded, and why:
    - `previous_hash`: concatenated separately per Section 41's own
      formula (`H(canonical(event) + previous_hash)`) -- not part of
      `canonical(event)` itself.
    - `current_hash`: the value being computed -- including it would be
      circular.
    - `created_at`: storage metadata (when the log *row* was persisted),
      not semantic content about the *operation* -- `started_at`/
      `completed_at` already capture the operation's own real timing.
      Also a genuine determinism risk: like every `DateTime(timezone=
      True)` column in this codebase, it round-trips through SQLite as
      timezone-naive, a database-specific artifact the task explicitly
      says to exclude ("Exclude nondeterministic database internals").
    """

    id: int
    case_id: int
    evidence_id: int | None
    job_id: int | None
    operation: str
    actor: str
    actor_type: str
    tool: str | None
    tool_version: str | None
    software_version: str | None
    parameters: dict[str, object] | None
    input_artifact_ids: list[int] | None
    output_artifact_ids: list[int] | None
    started_at: datetime | None
    completed_at: datetime | None
    status: str
    warnings: list[str] | None
    error: str | None
    notes: str | None
    description: str | None
    location_reference: str | None


def _canonical_datetime(value: datetime | None) -> str | None:
    """Normalize a datetime to a stable UTC ISO-8601 string.

    A naive datetime is treated as already-UTC (the established
    convention throughout this codebase: every `DateTime(timezone=True)`
    column round-trips through SQLite as naive) so the same event hashes
    identically whether it is canonicalized right after construction
    (still timezone-aware) or after being read back from the database
    (naive) -- never a spurious hash mismatch caused only by SQLite's own
    storage characteristic.

    Args:
        value: The datetime to normalize, or `None`.

    Returns:
        A UTC ISO-8601 string, or `None` if `value` is `None`.
    """
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()


def canonicalize_event(event: ChainableEvent) -> bytes:
    """Produce the exact, deterministic byte sequence hashed for one event.

    Field order in the resulting JSON object is alphabetical
    (`sort_keys=True`) -- deterministic independent of how the payload
    dict happens to be constructed, matching the JSON Canonicalization
    Scheme convention. Compact separators and ASCII-only escaping keep
    the output byte-for-byte identical across environments; the result is
    then UTF-8 encoded.

    Args:
        event: The event content to canonicalize.

    Returns:
        UTF-8-encoded canonical JSON bytes.
    """
    payload = {
        "id": event.id,
        "case_id": event.case_id,
        "evidence_id": event.evidence_id,
        "job_id": event.job_id,
        "operation": event.operation,
        "actor": event.actor,
        "actor_type": event.actor_type,
        "tool": event.tool,
        "tool_version": event.tool_version,
        "software_version": event.software_version,
        "parameters": event.parameters,
        "input_artifact_ids": event.input_artifact_ids,
        "output_artifact_ids": event.output_artifact_ids,
        "started_at": _canonical_datetime(event.started_at),
        "completed_at": _canonical_datetime(event.completed_at),
        "status": event.status,
        "warnings": event.warnings,
        "error": event.error,
        "notes": event.notes,
        "description": event.description,
        "location_reference": event.location_reference,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return text.encode("utf-8")


def compute_event_hash(event: ChainableEvent, *, previous_hash: str) -> str:
    """Compute one event's `current_hash`.

    Args:
        event: The event to hash.
        previous_hash: The preceding event's `current_hash`, or
            `GENESIS_PREVIOUS_HASH` for the first event in a chain.

    Returns:
        The lowercase hex SHA-256 digest of
        `canonicalize_event(event) + previous_hash.encode("utf-8")`.
    """
    canonical = canonicalize_event(event)
    return sha256_bytes(canonical + previous_hash.encode("utf-8"))


class ChainFailureReason(str, Enum):
    """Precise, diagnosable reasons `verify_chain` can report -- never a
    bare `False` (task Phase 16 scope: "Do not return only False with no
    diagnostic information")."""

    #: An event has no recorded `previous_hash`/`current_hash` at all.
    MISSING_HASH = "missing_hash"
    #: The first event's `previous_hash` is not `GENESIS_PREVIOUS_HASH`.
    INVALID_GENESIS = "invalid_genesis"
    #: An event's stored `previous_hash` does not match the immediately
    #: preceding event's real `current_hash`. Covers both "the preceding
    #: event's content was tampered" and "an event was deleted from the
    #: chain" -- a bare hash chain cannot cryptographically distinguish
    #: these two cases from stored state alone.
    BROKEN_LINK = "broken_link"
    #: Recomputing the hash from stored content does not match the
    #: stored `current_hash` -- covers direct content edits, direct
    #: `current_hash` edits, and canonicalization drift.
    CURRENT_HASH_MISMATCH = "current_hash_mismatch"
    #: Only produced when the caller supplies `expected_event_ids`: an
    #: expected id is absent from the actual chain.
    MISSING_EVENT = "missing_event"
    #: Only produced when the caller supplies `expected_event_ids`: an
    #: id present in the actual chain was not expected.
    UNEXPECTED_EVENT = "unexpected_event"
    #: Only produced when the caller supplies `expected_event_ids`: the
    #: same set of ids is present, but not in the expected order.
    REORDERED_EVENT = "reordered_event"


@dataclass(frozen=True)
class ChainFailure:
    """One diagnosed chain failure."""

    event_id: int | None
    reason: ChainFailureReason
    detail: str


@dataclass(frozen=True)
class ChainLink:
    """One event's position in a chain, paired with its stored hash values."""

    event: ChainableEvent
    stored_previous_hash: str | None
    stored_current_hash: str | None


@dataclass(frozen=True)
class ChainVerificationResult:
    """The full outcome of verifying one chain (task Phase 16 scope:
    "The verification result should identify: case ID, chain scope,
    event count, first event, last event, chain validity, first invalid
    event if any, failure reason")."""

    valid: bool
    event_count: int
    first_event_id: int | None
    last_event_id: int | None
    failure: ChainFailure | None
    case_id: int | None = None
    chain_scope: str = CHAIN_SCOPE


def verify_chain(
    links: list[ChainLink], *, expected_event_ids: list[int] | None = None
) -> ChainVerificationResult:
    """Verify a chain of events, in the caller-supplied (already-ordered) sequence.

    Reports the *first* failure encountered while walking the chain in
    order (task: "Verification must report where the chain first
    fails."). A middle event is never reported valid merely because its
    own `current_hash` recomputes correctly when its link to the
    predecessor is broken -- both checks run for every event, in order,
    before moving on.

    Args:
        links: The chain's events, already ordered (by `ProcessingEvent.
            id` ascending -- see `app.core.audit_chain_manager` for the
            ordering rationale). This function trusts the given order;
            it does not re-sort.
        expected_event_ids: An optional independently-known expected
            sequence of event ids (e.g. from a prior snapshot). When
            given, enables `MISSING_EVENT`/`UNEXPECTED_EVENT`/
            `REORDERED_EVENT` detection. Without it, an appended event is
            correctly treated as normal chain growth, not tampering.

    Returns:
        A `ChainVerificationResult` (without `case_id` -- the DB-aware
        caller fills that in).
    """
    if expected_event_ids is not None:
        actual_ids = [link.event.id for link in links]
        actual_set = set(actual_ids)
        expected_set = set(expected_event_ids)

        missing = [eid for eid in expected_event_ids if eid not in actual_set]
        if missing:
            return ChainVerificationResult(
                valid=False,
                event_count=len(links),
                first_event_id=links[0].event.id if links else None,
                last_event_id=links[-1].event.id if links else None,
                failure=ChainFailure(
                    event_id=missing[0],
                    reason=ChainFailureReason.MISSING_EVENT,
                    detail=f"expected event {missing[0]} is absent from the chain",
                ),
            )

        unexpected = [eid for eid in actual_ids if eid not in expected_set]
        if unexpected:
            return ChainVerificationResult(
                valid=False,
                event_count=len(links),
                first_event_id=links[0].event.id if links else None,
                last_event_id=links[-1].event.id if links else None,
                failure=ChainFailure(
                    event_id=unexpected[0],
                    reason=ChainFailureReason.UNEXPECTED_EVENT,
                    detail=f"event {unexpected[0]} was not in the expected set",
                ),
            )

        if actual_ids != expected_event_ids:
            return ChainVerificationResult(
                valid=False,
                event_count=len(links),
                first_event_id=links[0].event.id if links else None,
                last_event_id=links[-1].event.id if links else None,
                failure=ChainFailure(
                    event_id=None,
                    reason=ChainFailureReason.REORDERED_EVENT,
                    detail=f"expected order {expected_event_ids}, found {actual_ids}",
                ),
            )

    if not links:
        return ChainVerificationResult(
            valid=True, event_count=0, first_event_id=None, last_event_id=None, failure=None
        )

    first_event_id = links[0].event.id
    last_event_id = links[-1].event.id
    expected_previous = GENESIS_PREVIOUS_HASH

    for index, link in enumerate(links):
        event_id = link.event.id

        if link.stored_previous_hash is None or link.stored_current_hash is None:
            return ChainVerificationResult(
                valid=False,
                event_count=len(links),
                first_event_id=first_event_id,
                last_event_id=last_event_id,
                failure=ChainFailure(
                    event_id=event_id,
                    reason=ChainFailureReason.MISSING_HASH,
                    detail="event has no previous_hash/current_hash recorded",
                ),
            )

        if link.stored_previous_hash != expected_previous:
            reason = (
                ChainFailureReason.INVALID_GENESIS if index == 0 else ChainFailureReason.BROKEN_LINK
            )
            detail = (
                f"expected previous_hash {expected_previous!r}, "
                f"found {link.stored_previous_hash!r}"
            )
            if reason is ChainFailureReason.BROKEN_LINK:
                detail += (
                    " (indicates either the preceding event's content changed or an "
                    "event was deleted from the chain -- these are indistinguishable "
                    "from stored state alone)"
                )
            return ChainVerificationResult(
                valid=False,
                event_count=len(links),
                first_event_id=first_event_id,
                last_event_id=last_event_id,
                failure=ChainFailure(event_id=event_id, reason=reason, detail=detail),
            )

        recomputed = compute_event_hash(link.event, previous_hash=link.stored_previous_hash)
        if recomputed != link.stored_current_hash:
            return ChainVerificationResult(
                valid=False,
                event_count=len(links),
                first_event_id=first_event_id,
                last_event_id=last_event_id,
                failure=ChainFailure(
                    event_id=event_id,
                    reason=ChainFailureReason.CURRENT_HASH_MISMATCH,
                    detail=(
                        f"recomputed hash {recomputed!r} does not match stored "
                        f"current_hash {link.stored_current_hash!r}"
                    ),
                ),
            )

        expected_previous = link.stored_current_hash

    return ChainVerificationResult(
        valid=True,
        event_count=len(links),
        first_event_id=first_event_id,
        last_event_id=last_event_id,
        failure=None,
    )
