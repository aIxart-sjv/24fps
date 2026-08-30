"""Tests for `app.blockchain.provider`: `LocalTestBlockchainProvider` and
the `get_blockchain_provider` factory. No database, no network.
"""

from __future__ import annotations

import pytest

from app.blockchain.anchor import AnchorStatus
from app.blockchain.provider import (
    AnchorNotFoundError,
    BlockchainProviderNotConfiguredError,
    LocalTestBlockchainProvider,
    get_blockchain_provider,
)


# ---- LocalTestBlockchainProvider ------------------------------------------


def test_create_anchor_returns_local_test_status() -> None:
    provider = LocalTestBlockchainProvider()
    submission = provider.create_anchor("a" * 64, metadata={"case_id": 1})
    assert submission.status == AnchorStatus.LOCAL_TEST
    assert submission.status != AnchorStatus.CONFIRMED


def test_create_anchor_transaction_reference_is_unmistakably_local() -> None:
    provider = LocalTestBlockchainProvider()
    submission = provider.create_anchor("a" * 64, metadata={})
    assert submission.transaction_reference.startswith("LOCAL-TEST-ANCHOR-")
    assert not submission.transaction_reference.startswith("0x")


def test_create_anchor_references_are_unique() -> None:
    provider = LocalTestBlockchainProvider()
    s1 = provider.create_anchor("a" * 64, metadata={})
    s2 = provider.create_anchor("a" * 64, metadata={})
    assert s1.transaction_reference != s2.transaction_reference


def test_get_anchor_returns_what_was_submitted() -> None:
    provider = LocalTestBlockchainProvider()
    submission = provider.create_anchor("c" * 64, metadata={})
    record = provider.get_anchor(submission.transaction_reference)
    assert record.anchor_hash == "c" * 64
    assert record.transaction_reference == submission.transaction_reference
    assert record.status == AnchorStatus.LOCAL_TEST


def test_get_anchor_missing_reference_raises() -> None:
    provider = LocalTestBlockchainProvider()
    with pytest.raises(AnchorNotFoundError):
        provider.get_anchor("LOCAL-TEST-ANCHOR-doesnotexist")


def test_verify_anchor_true_when_hash_matches() -> None:
    provider = LocalTestBlockchainProvider()
    submission = provider.create_anchor("d" * 64, metadata={})
    assert provider.verify_anchor("d" * 64, submission.transaction_reference) is True


def test_verify_anchor_false_when_hash_differs() -> None:
    provider = LocalTestBlockchainProvider()
    submission = provider.create_anchor("d" * 64, metadata={})
    assert provider.verify_anchor("e" * 64, submission.transaction_reference) is False


def test_verify_anchor_false_when_reference_unknown() -> None:
    provider = LocalTestBlockchainProvider()
    assert provider.verify_anchor("d" * 64, "LOCAL-TEST-ANCHOR-unknown") is False


def test_provider_status_reports_non_real() -> None:
    provider = LocalTestBlockchainProvider()
    status = provider.provider_status()
    assert status.available is True
    assert status.provider_name == "local_testnet"
    assert "not" in status.detail.lower() or "local" in status.detail.lower()


def test_provider_ledger_is_independent_per_instance() -> None:
    """Two separate provider instances never see each other's anchors --
    each is its own independent external ledger."""
    provider_a = LocalTestBlockchainProvider()
    provider_b = LocalTestBlockchainProvider()
    submission = provider_a.create_anchor("f" * 64, metadata={})
    with pytest.raises(AnchorNotFoundError):
        provider_b.get_anchor(submission.transaction_reference)


# ---- get_blockchain_provider factory --------------------------------------


def test_factory_raises_when_provider_is_none() -> None:
    with pytest.raises(BlockchainProviderNotConfiguredError):
        get_blockchain_provider(provider_name="none")


def test_factory_raises_when_provider_is_empty() -> None:
    with pytest.raises(BlockchainProviderNotConfiguredError):
        get_blockchain_provider(provider_name="")


def test_factory_raises_for_unimplemented_real_network() -> None:
    with pytest.raises(BlockchainProviderNotConfiguredError, match="PENDING"):
        get_blockchain_provider(provider_name="ethereum")


def test_factory_resolves_local_testnet() -> None:
    provider = get_blockchain_provider(provider_name="local_testnet", network="unit-test-net")
    assert isinstance(provider, LocalTestBlockchainProvider)
    assert provider.provider_status().available is True


def test_factory_returns_shared_instance_for_same_network() -> None:
    p1 = get_blockchain_provider(provider_name="local_testnet", network="shared-net-1")
    p2 = get_blockchain_provider(provider_name="local_testnet", network="shared-net-1")
    assert p1 is p2
