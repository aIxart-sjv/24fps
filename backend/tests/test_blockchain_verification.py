"""Pure-logic tests for `app.blockchain.verification.compare_anchor_state`.
No database, no HTTP, no provider I/O -- inputs are hand-built.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.audit.hash_chain import ChainFailure, ChainFailureReason, ChainVerificationResult
from app.blockchain.verification import (
    AnchorVerificationOutcome,
    compare_anchor_state,
    provider_unavailable_result,
)

_NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
_VALID_CHAIN = ChainVerificationResult(
    valid=True, event_count=3, first_event_id=1, last_event_id=3, failure=None
)
_INVALID_CHAIN = ChainVerificationResult(
    valid=False,
    event_count=3,
    first_event_id=1,
    last_event_id=3,
    failure=ChainFailure(
        event_id=2, reason=ChainFailureReason.CURRENT_HASH_MISMATCH, detail="tampered"
    ),
)


def _compare(**overrides: object) -> object:
    kwargs: dict[str, object] = dict(
        anchor_id=1,
        case_id=1,
        expected_hash="a" * 64,
        anchored_hash="a" * 64,
        chain_result=_VALID_CHAIN,
        provider_name="local_testnet",
        network="local",
        transaction_reference="LOCAL-TEST-ANCHOR-xyz",
        checked_at=_NOW,
    )
    kwargs.update(overrides)
    return compare_anchor_state(**kwargs)  # type: ignore[arg-type]


def test_valid_when_hashes_match_and_chain_valid() -> None:
    result = _compare()
    assert result.valid is True
    assert result.outcome == AnchorVerificationOutcome.VALID
    assert result.expected_hash == "a" * 64
    assert result.anchored_hash == "a" * 64


def test_hash_mismatch_when_expected_differs_from_anchored() -> None:
    result = _compare(expected_hash="b" * 64, anchored_hash="a" * 64)
    assert result.valid is False
    assert result.outcome == AnchorVerificationOutcome.HASH_MISMATCH
    assert result.chain_valid is True


def test_anchor_not_found_when_anchored_hash_is_none() -> None:
    result = _compare(anchored_hash=None)
    assert result.valid is False
    assert result.outcome == AnchorVerificationOutcome.ANCHOR_NOT_FOUND
    assert result.anchored_hash is None


def test_chain_invalid_takes_priority_even_if_hashes_match() -> None:
    """A chain known to be broken is never certified valid just because
    one derived fingerprint happens to still match."""
    result = _compare(chain_result=_INVALID_CHAIN, expected_hash="a" * 64, anchored_hash="a" * 64)
    assert result.valid is False
    assert result.outcome == AnchorVerificationOutcome.CHAIN_INVALID
    assert result.chain_valid is False
    assert result.chain_failure is not None
    assert result.chain_failure.event_id == 2


def test_chain_invalid_reported_even_when_hashes_also_differ() -> None:
    result = _compare(chain_result=_INVALID_CHAIN, expected_hash="b" * 64, anchored_hash="a" * 64)
    assert result.valid is False
    assert result.outcome == AnchorVerificationOutcome.CHAIN_INVALID


def test_result_always_carries_anchor_and_case_identifiers() -> None:
    result = _compare(anchor_id=42, case_id=99)
    assert result.anchor_id == 42
    assert result.case_id == 99


def test_result_carries_provider_network_and_transaction_reference() -> None:
    result = _compare(
        provider_name="local_testnet",
        network="test-net-1",
        transaction_reference="LOCAL-TEST-ANCHOR-abc",
    )
    assert result.provider_name == "local_testnet"
    assert result.network == "test-net-1"
    assert result.transaction_reference == "LOCAL-TEST-ANCHOR-abc"


def test_result_detail_is_never_empty() -> None:
    for outcome_kwargs in (
        {},
        {"anchored_hash": None},
        {"chain_result": _INVALID_CHAIN},
        {"expected_hash": "z" * 64},
    ):
        result = _compare(**outcome_kwargs)
        assert result.detail


# ---- provider_unavailable_result ------------------------------------------


def test_provider_unavailable_result_is_never_valid() -> None:
    result = provider_unavailable_result(
        anchor_id=1,
        case_id=1,
        chain_result=_VALID_CHAIN,
        provider_name="local_testnet",
        network="local",
        transaction_reference="LOCAL-TEST-ANCHOR-xyz",
        checked_at=_NOW,
        detail="provider not configured",
    )
    assert result.valid is False
    assert result.outcome == AnchorVerificationOutcome.PROVIDER_UNAVAILABLE
    assert result.expected_hash is None
    assert result.anchored_hash is None
    assert result.chain_valid is True  # still reports the chain check that did run
