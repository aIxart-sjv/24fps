"""
Blockchain provider abstraction (Phase 17, Master Specification Section 42
"Blockchain Anchoring").

The application must never depend directly on one blockchain network.
This module defines the minimal `BlockchainProvider` interface Section 42
documents (`create_anchor`, `get_anchor`, `verify_anchor`,
`provider_status`) plus one fully-working, fully offline implementation:
`LocalTestBlockchainProvider`. It never claims a real blockchain
transaction occurred (task Phase 17 scope section 7) and never generates
a reference that could be mistaken for a real public-chain transaction
hash.

No real network provider is implemented in this phase. No specific
blockchain/network is mandated anywhere in the project documentation
(`docs/SIH_TECH_STACK.md` Section 16 explicitly lists "Private
blockchain" as *future* scope), and this codebase has no blockchain SDK
dependency installed. Rather than lock the project to an arbitrary paid
production chain, `get_blockchain_provider` resolves the configured
`BLOCKCHAIN_PROVIDER`/`BLOCKCHAIN_NETWORK` settings (`app.config.
Settings`) to `LocalTestBlockchainProvider` when a local/test provider is
requested, and raises a controlled `BlockchainProviderNotConfiguredError`
-- never a fabricated result -- for anything else, including the
default "none" (blockchain anchoring intentionally unavailable; Phase 16
local hash-chain integrity keeps operating regardless, per Section 42's
own closing rule: "The project must remain usable if blockchain
infrastructure is unavailable").
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from app.blockchain.anchor import AnchorStatus

__all__ = [
    "AnchorNotFoundError",
    "AnchorRecord",
    "AnchorSubmission",
    "AnchorSubmissionError",
    "BlockchainProvider",
    "BlockchainProviderError",
    "BlockchainProviderNotConfiguredError",
    "LocalTestBlockchainProvider",
    "ProviderStatus",
    "get_blockchain_provider",
]


class BlockchainProviderError(Exception):
    """Base class for controlled blockchain-provider failures. A
    provider must always raise one of these (or return an explicit
    failure status) rather than silently claim success."""


class AnchorSubmissionError(BlockchainProviderError):
    """A provider could not accept/submit an anchor (rejected
    transaction, timeout, invalid credentials, malformed response)."""


class AnchorNotFoundError(BlockchainProviderError):
    """The referenced transaction does not exist at this provider."""


class BlockchainProviderNotConfiguredError(BlockchainProviderError):
    """No usable blockchain provider is configured. Raised instead of
    ever fabricating a real-provider result (task Phase 17 scope
    section 33: "do NOT fabricate a real blockchain result... Report
    real-network validation as PENDING / NOT CONFIGURED")."""


@dataclass(frozen=True)
class AnchorSubmission:
    """What a provider returns immediately after `create_anchor`."""

    anchor_hash: str
    transaction_reference: str
    provider_name: str
    network: str
    status: AnchorStatus
    submitted_at: datetime
    detail: str


@dataclass(frozen=True)
class AnchorRecord:
    """What a provider returns when a previously-submitted anchor is
    looked up again via `get_anchor`."""

    transaction_reference: str
    anchor_hash: str
    provider_name: str
    network: str
    status: AnchorStatus
    retrieved_at: datetime
    detail: str


@dataclass(frozen=True)
class ProviderStatus:
    """Whether a provider is currently usable, independent of any one
    anchor -- Section 42's documented `provider_status()` operation."""

    available: bool
    provider_name: str
    network: str
    detail: str


class BlockchainProvider(ABC):
    """Minimal blockchain-anchoring provider interface (Master
    Specification Section 42). Concrete providers are infrastructure
    (Section 81): the domain/application layers above never construct
    network requests themselves, only call these four operations."""

    provider_name: str

    @abstractmethod
    def create_anchor(self, anchor_hash: str, metadata: dict[str, Any]) -> AnchorSubmission:
        """Submit one anchor fingerprint to this provider.

        Args:
            anchor_hash: The SHA-256 anchor hash to anchor (see
                `app.blockchain.anchor.compute_anchor_hash`). Never the
                evidence itself.
            metadata: Small, non-secret descriptive metadata (e.g. case
                identifier, chain identifier, event count). Must never
                include CCTV content, raw forensic artifacts, or secrets.

        Returns:
            The submission result.

        Raises:
            AnchorSubmissionError: If the provider rejects/cannot accept
                the submission.
        """
        raise NotImplementedError

    @abstractmethod
    def get_anchor(self, transaction_reference: str) -> AnchorRecord:
        """Retrieve a previously-submitted anchor by its reference.

        Args:
            transaction_reference: The reference returned by an earlier
                `create_anchor` call.

        Returns:
            The stored anchor record.

        Raises:
            AnchorNotFoundError: If no such transaction is known to this
                provider.
        """
        raise NotImplementedError

    @abstractmethod
    def verify_anchor(self, anchor_hash: str, transaction_reference: str) -> bool:
        """Convenience check: does `transaction_reference` anchor exactly
        `anchor_hash` at this provider? Equivalent to `get_anchor(...)
        .anchor_hash == anchor_hash`, but a provider may implement it
        more directly (e.g. a real network's own verification RPC).

        Args:
            anchor_hash: The hash to check for.
            transaction_reference: The transaction to check.

        Returns:
            `True` if the provider's own record for that transaction
            matches `anchor_hash`; `False` if it does not or the
            transaction is unknown to this provider (never raises for
            "not found" here -- callers that need to distinguish "not
            found" from "found but different" should use `get_anchor`).
        """
        raise NotImplementedError

    @abstractmethod
    def provider_status(self) -> ProviderStatus:
        """Report whether this provider is currently usable."""
        raise NotImplementedError


class LocalTestBlockchainProvider(BlockchainProvider):
    """Deterministic, fully offline provider for development and tests.

    Keeps its own in-memory ledger, independent of the application's own
    database -- `get_anchor`/`verify_anchor` genuinely read back only
    what was previously submitted through `create_anchor`, exactly like
    an external system would, without ever touching the app's own
    `blockchain_anchors` table.

    This is explicitly NOT a real blockchain: transaction references are
    generated with an unmistakable `LOCAL-TEST-ANCHOR-` prefix (never a
    plausible `0x`-prefixed public-chain hash), `provider_status()`
    always reports it as a non-real provider, and it always returns
    `AnchorStatus.LOCAL_TEST` -- never `CONFIRMED` (task Phase 17 scope
    section 7 / section 12: never report `CONFIRMED` merely because a
    call returned without raising).

    The ledger lives only in this process's memory for this instance's
    lifetime -- it does not survive a process restart. That is an
    intentional, honestly-documented limitation of a *test* double, not
    a claim about how a real provider would behave.
    """

    provider_name = "local_testnet"

    def __init__(self, network: str = "local") -> None:
        self._network = network
        self._ledger: dict[str, AnchorRecord] = {}

    def create_anchor(self, anchor_hash: str, metadata: dict[str, Any]) -> AnchorSubmission:
        transaction_reference = f"LOCAL-TEST-ANCHOR-{uuid.uuid4().hex}"
        submitted_at = datetime.now(UTC)
        detail = "deterministic local/test ledger entry -- not a real blockchain transaction"
        record = AnchorRecord(
            transaction_reference=transaction_reference,
            anchor_hash=anchor_hash,
            provider_name=self.provider_name,
            network=self._network,
            status=AnchorStatus.LOCAL_TEST,
            retrieved_at=submitted_at,
            detail=detail,
        )
        self._ledger[transaction_reference] = record
        return AnchorSubmission(
            anchor_hash=anchor_hash,
            transaction_reference=transaction_reference,
            provider_name=self.provider_name,
            network=self._network,
            status=AnchorStatus.LOCAL_TEST,
            submitted_at=submitted_at,
            detail=detail,
        )

    def get_anchor(self, transaction_reference: str) -> AnchorRecord:
        record = self._ledger.get(transaction_reference)
        if record is None:
            raise AnchorNotFoundError(
                f"no local/test anchor found for transaction reference "
                f"{transaction_reference!r}"
            )
        return record

    def verify_anchor(self, anchor_hash: str, transaction_reference: str) -> bool:
        record = self._ledger.get(transaction_reference)
        if record is None:
            return False
        return record.anchor_hash == anchor_hash

    def provider_status(self) -> ProviderStatus:
        return ProviderStatus(
            available=True,
            provider_name=self.provider_name,
            network=self._network,
            detail="deterministic local/test provider; does not use a real blockchain network",
        )


@lru_cache(maxsize=8)
def _local_test_provider_singleton(network: str) -> LocalTestBlockchainProvider:
    """One shared in-memory ledger per configured network name for the
    life of this process -- mirrors `app.config.get_settings`'s
    `lru_cache` pattern so repeated calls within one running application
    observe the same local/test ledger."""
    return LocalTestBlockchainProvider(network=network)


def get_blockchain_provider(
    *, provider_name: str | None = None, network: str | None = None
) -> BlockchainProvider:
    """Resolve the configured `BlockchainProvider` implementation.

    Reads `app.config.Settings.blockchain_provider`/`blockchain_network`
    unless explicitly overridden (tests and callers that want an
    isolated, non-shared ledger should construct
    `LocalTestBlockchainProvider()` directly instead of going through
    this factory).

    Args:
        provider_name: Override for `settings.blockchain_provider`.
        network: Override for `settings.blockchain_network`.

    Returns:
        A usable `BlockchainProvider`.

    Raises:
        BlockchainProviderNotConfiguredError: If no provider is
            configured (`"none"`, the default) or if a real network
            provider is named that this phase does not implement. Never
            fabricates a substitute result.
    """
    from app.config import get_settings

    settings = get_settings()
    name = provider_name if provider_name is not None else settings.blockchain_provider
    name = name.strip().lower()
    resolved_network = network if network is not None else settings.blockchain_network

    if name in ("", "none"):
        raise BlockchainProviderNotConfiguredError(
            "no blockchain provider is configured (BLOCKCHAIN_PROVIDER=none); "
            "blockchain anchoring is unavailable in this deployment -- local "
            "Phase 16 hash-chain integrity still operates independently"
        )
    if name in ("local_testnet", "local", "test"):
        return _local_test_provider_singleton(resolved_network or "local")

    raise BlockchainProviderNotConfiguredError(
        f"blockchain provider {name!r} is not implemented in Phase 17 "
        "(PENDING / NOT CONFIGURED); only 'local_testnet' (or 'none' to "
        "disable blockchain anchoring) is supported"
    )
