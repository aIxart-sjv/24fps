"""
Blockchain anchoring vocabulary (Phase 17, Master Specification Section 42
"Blockchain Anchoring").

Mirrors `app.audit`'s role for Phase 15/16: this package re-exports the
pure, DB-free vocabulary and abstractions
(`app.blockchain.anchor`/`provider`/`verification`) that
`app.core.blockchain_manager.BlockchainManager` (the DB-aware
orchestration layer) is built on top of.

Module ownership (Master Specification Section 79): "Module: Blockchain
-- Owns: anchoring, verification." Provenance/hash-chain history
(Phases 15/16) is explicitly not re-implemented here -- only reused.
"""

from __future__ import annotations

from app.blockchain.anchor import AnchorableChainState, AnchorStatus, EmptyChainStateError
from app.blockchain.provider import (
    AnchorNotFoundError,
    AnchorRecord,
    AnchorSubmission,
    AnchorSubmissionError,
    BlockchainProvider,
    BlockchainProviderError,
    BlockchainProviderNotConfiguredError,
    LocalTestBlockchainProvider,
    ProviderStatus,
    get_blockchain_provider,
)
from app.blockchain.verification import AnchorVerificationOutcome, AnchorVerificationResult

__all__ = [
    "AnchorNotFoundError",
    "AnchorRecord",
    "AnchorStatus",
    "AnchorSubmission",
    "AnchorSubmissionError",
    "AnchorVerificationOutcome",
    "AnchorVerificationResult",
    "AnchorableChainState",
    "BlockchainProvider",
    "BlockchainProviderError",
    "BlockchainProviderNotConfiguredError",
    "EmptyChainStateError",
    "LocalTestBlockchainProvider",
    "ProviderStatus",
    "get_blockchain_provider",
]
