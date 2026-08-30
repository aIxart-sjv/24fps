"""
Blockchain anchor verification (Phase 17, Master Specification Section 42
"Blockchain Anchoring").

Pure decision logic: given a freshly-recomputed local chain state hash,
whatever the configured provider currently reports for the anchor's
transaction reference, and the Phase 16 chain's own current validity,
decide whether the anchor still holds. No DB, no HTTP, no provider I/O
here -- `app.core.blockchain_manager.BlockchainManager.verify_anchor` is
the DB/provider-aware caller that gathers these three inputs and calls
`compare_anchor_state`.

Reports precisely where verification fails, mirroring
`app.audit.hash_chain.verify_chain`'s own diagnostic style (task Phase 17
scope section 13: "If the provider cannot retrieve the referenced
transaction: return a controlled verification failure" -- never a bare
`False`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.audit.hash_chain import ChainFailure, ChainVerificationResult

__all__ = [
    "AnchorVerificationOutcome",
    "AnchorVerificationResult",
    "compare_anchor_state",
    "provider_unavailable_result",
]


class AnchorVerificationOutcome(str, Enum):
    """Precise, diagnosable reasons `compare_anchor_state` can report.

    Never persisted on `BlockchainAnchor.status` (see
    `app.blockchain.anchor.AnchorStatus`'s docstring for why) -- this is
    the outcome of one verification *check*, repeatable and
    side-effect-free, not the anchor's own creation-time lifecycle.
    """

    #: Local chain state (recomputed) matches the externally anchored hash.
    VALID = "valid"
    #: Local chain state (recomputed) no longer matches the externally
    #: anchored hash -- the local audit history has changed since anchoring.
    HASH_MISMATCH = "hash_mismatch"
    #: The local Phase 16 audit chain itself does not currently verify.
    #: No comparison built on top of a known-broken chain can be trusted,
    #: even if the recomputed hash happens to still match.
    CHAIN_INVALID = "chain_invalid"
    #: The provider has no record of the anchor's transaction reference.
    ANCHOR_NOT_FOUND = "anchor_not_found"
    #: The provider itself could not be reached/resolved.
    PROVIDER_UNAVAILABLE = "provider_unavailable"


@dataclass(frozen=True)
class AnchorVerificationResult:
    """The full outcome of verifying one recorded anchor (task Phase 17
    scope section 13: case ID, expected vs. anchored hash, validity, and
    a structured reason -- never only `True`/`False`)."""

    valid: bool
    outcome: AnchorVerificationOutcome
    anchor_id: int
    case_id: int
    expected_hash: str | None
    anchored_hash: str | None
    chain_valid: bool
    chain_failure: ChainFailure | None
    provider_name: str
    network: str
    transaction_reference: str
    checked_at: datetime
    detail: str


def compare_anchor_state(
    *,
    anchor_id: int,
    case_id: int,
    expected_hash: str,
    anchored_hash: str | None,
    chain_result: ChainVerificationResult,
    provider_name: str,
    network: str,
    transaction_reference: str,
    checked_at: datetime,
) -> AnchorVerificationResult:
    """Decide whether a recorded anchor still holds.

    A middle-ground case is deliberately not treated as valid: if the
    local Phase 16 chain no longer verifies, the result is
    `CHAIN_INVALID` even when the recomputed hash happens to still equal
    the anchored one -- an already-known-broken chain cannot be
    certified sound just because one derived fingerprint matched (task
    Phase 17 scope section 3's "do not anchor an invalid chain" extends
    naturally to "do not certify one as still valid" either).

    Args:
        anchor_id: The `BlockchainAnchor` row being checked.
        case_id: The case it belongs to.
        expected_hash: The freshly recomputed local chain-state hash
            (`app.blockchain.anchor.compute_anchor_hash` over the
            *current* event content).
        anchored_hash: The hash the provider currently reports for
            `transaction_reference`, or `None` if the provider has no
            record of it.
        chain_result: The current Phase 16 `verify_case_chain` result
            for this case.
        provider_name: The provider that was checked.
        network: The network the anchor was submitted to.
        transaction_reference: The anchor's transaction reference.
        checked_at: When this check was performed.

    Returns:
        A structured `AnchorVerificationResult`.
    """
    if anchored_hash is None:
        return AnchorVerificationResult(
            valid=False,
            outcome=AnchorVerificationOutcome.ANCHOR_NOT_FOUND,
            anchor_id=anchor_id,
            case_id=case_id,
            expected_hash=expected_hash,
            anchored_hash=None,
            chain_valid=chain_result.valid,
            chain_failure=chain_result.failure,
            provider_name=provider_name,
            network=network,
            transaction_reference=transaction_reference,
            checked_at=checked_at,
            detail="the blockchain provider has no record of this transaction reference",
        )

    if not chain_result.valid:
        failure_reason = chain_result.failure.reason.value if chain_result.failure else "unknown"
        return AnchorVerificationResult(
            valid=False,
            outcome=AnchorVerificationOutcome.CHAIN_INVALID,
            anchor_id=anchor_id,
            case_id=case_id,
            expected_hash=expected_hash,
            anchored_hash=anchored_hash,
            chain_valid=False,
            chain_failure=chain_result.failure,
            provider_name=provider_name,
            network=network,
            transaction_reference=transaction_reference,
            checked_at=checked_at,
            detail=(
                f"the local Phase 16 audit chain itself no longer verifies "
                f"({failure_reason}); no anchor comparison can be trusted while "
                "the local chain is broken"
            ),
        )

    if expected_hash != anchored_hash:
        return AnchorVerificationResult(
            valid=False,
            outcome=AnchorVerificationOutcome.HASH_MISMATCH,
            anchor_id=anchor_id,
            case_id=case_id,
            expected_hash=expected_hash,
            anchored_hash=anchored_hash,
            chain_valid=True,
            chain_failure=None,
            provider_name=provider_name,
            network=network,
            transaction_reference=transaction_reference,
            checked_at=checked_at,
            detail=(
                f"recomputed local chain state {expected_hash!r} does not match "
                f"the anchored hash {anchored_hash!r} -- local audit history no "
                "longer matches what was anchored"
            ),
        )

    return AnchorVerificationResult(
        valid=True,
        outcome=AnchorVerificationOutcome.VALID,
        anchor_id=anchor_id,
        case_id=case_id,
        expected_hash=expected_hash,
        anchored_hash=anchored_hash,
        chain_valid=True,
        chain_failure=None,
        provider_name=provider_name,
        network=network,
        transaction_reference=transaction_reference,
        checked_at=checked_at,
        detail="local audit chain state matches the anchored fingerprint",
    )


def provider_unavailable_result(
    *,
    anchor_id: int,
    case_id: int,
    chain_result: ChainVerificationResult,
    provider_name: str,
    network: str,
    transaction_reference: str,
    checked_at: datetime,
    detail: str,
) -> AnchorVerificationResult:
    """Build the controlled failure result for when the provider itself
    could not be reached/resolved -- there is no `expected_hash`/
    `anchored_hash` to compare because the check never got that far.
    `chain_result` is still reported for transparency (the local Phase
    16 chain check runs before provider resolution is attempted, so this
    information is already available)."""
    return AnchorVerificationResult(
        valid=False,
        outcome=AnchorVerificationOutcome.PROVIDER_UNAVAILABLE,
        anchor_id=anchor_id,
        case_id=case_id,
        expected_hash=None,
        anchored_hash=None,
        chain_valid=chain_result.valid,
        chain_failure=chain_result.failure,
        provider_name=provider_name,
        network=network,
        transaction_reference=transaction_reference,
        checked_at=checked_at,
        detail=detail,
    )
