"""
Business logic for blockchain anchoring (Phase 17).
Master Specification Section 42 ("Blockchain Anchoring").

This is the DB-aware orchestration layer built on `app.blockchain.*`
(the pure anchor-representation/provider-abstraction/verification
vocabulary) and on Phase 16's `app.core.audit_chain_manager.
AuditChainManager` (never reimplemented here). It never creates a
`ProcessingEvent` itself outside of `app.core.provenance_manager.
ProvenanceManager.record_event` -- no competing provenance path.

============================================================================
ORDERING, AND WHY IT IS NOT CIRCULAR (task Phase 17 scope section 24)
============================================================================
    1. AuditChainManager.verify_case_chain(db, case_id)  -- must be valid
    2. fetch this case's events, fold them into the current chain state
    3. compute anchor_hash from that state
    4. submit anchor_hash to the provider
    5. persist the BlockchainAnchor row
    6. record a ProcessingEvent describing the anchoring action itself

Step 6 appends a *new* event to the case's Phase 16 chain -- but step 3
already captured and hashed the chain state as it stood *before* that
new event exists. The anchor therefore commits to "the chain through
event N"; step 6's event becomes event N+1, a later, independent
extension that simply points back at event N's hash like any other new
event would. It is never included in, and never changes, what was
already anchored. Nothing here ever recomputes or rewrites an earlier
event's stored hash to make an anchor "fit" -- that would be exactly the
silent-reseal behavior Phase 16 forbids.

============================================================================
WHY A CHAIN MUST VERIFY BEFORE IT CAN BE ANCHORED (section 3)
============================================================================
Anchoring an already-known-tampered chain would externally certify
something false. `create_anchor` therefore always runs `AuditChainManager
.verify_case_chain` first and refuses (raises, persists nothing) if the
chain is not valid or has no events yet.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.audit import ActorType, ProcessingOperation
from app.audit.hash_chain import ChainFailure, ChainFailureReason, ChainVerificationResult
from app.blockchain.anchor import (
    EmptyChainStateError,
    compute_anchor_hash,
    recompute_latest_chain_state,
)
from app.blockchain.provider import (
    AnchorNotFoundError,
    AnchorSubmissionError,
    BlockchainProvider,
    BlockchainProviderError,
    BlockchainProviderNotConfiguredError,
    get_blockchain_provider,
)
from app.blockchain.verification import (
    AnchorVerificationResult,
    compare_anchor_state,
    provider_unavailable_result,
)
from app.core.audit_chain_manager import AuditChainManager, _to_chainable
from app.core.case_manager import CaseManager
from app.core.provenance_manager import ProvenanceManager
from app.models import BlockchainAnchor, JobStatus, ProcessingEvent

__all__ = [
    "BlockchainManager",
    "ChainNotValidForAnchoringError",
]


class ChainNotValidForAnchoringError(ValueError):
    """Raised when `create_anchor` is asked to anchor a case whose
    Phase 16 audit chain does not currently verify, or has no recorded
    events -- an anchor is never created in either situation."""


@dataclass(frozen=True)
class _ChainStateForAnchor:
    """Internal: the chain-state hash plus the payload persisted onto
    `BlockchainAnchor`/passed to the provider."""

    anchor_hash: str
    event_count: int
    last_event_id: int


class BlockchainManager:
    """Service layer for creating and verifying blockchain anchors of a
    case's Phase 16 hash-linked audit chain."""

    # ---- Internal: chain-state recomputation (shared by create/verify) --

    @staticmethod
    def _recompute_chain_state(
        db: Session, case_id: int, *, up_to_event_id: int | None = None
    ) -> _ChainStateForAnchor:
        """Fold the case's events into a chain state and hash it.

        Args:
            db: Database session.
            case_id: The case to fold events for.
            up_to_event_id: When given, only events with `id <=
                up_to_event_id` are included -- this is how `verify_anchor`
                recomputes the *exact same prefix* an earlier anchor
                captured, rather than "everything that currently exists"
                (which would always differ once even one more event, such
                as the anchoring action's own `ProcessingEvent`, has been
                appended since). `None` (the default, used by
                `create_anchor`) means "every event that exists right now."

        Raises:
            EmptyChainStateError: If no matching events exist.
        """
        query = db.query(ProcessingEvent).filter(ProcessingEvent.case_id == case_id)
        if up_to_event_id is not None:
            query = query.filter(ProcessingEvent.id <= up_to_event_id)
        events = query.order_by(ProcessingEvent.id.asc()).all()
        chainable = [_to_chainable(event) for event in events]
        state = recompute_latest_chain_state(case_id, chainable)
        return _ChainStateForAnchor(
            anchor_hash=compute_anchor_hash(state),
            event_count=state.event_count,
            last_event_id=state.last_event_id,
        )

    # ---- Creating an anchor ----------------------------------------------

    @staticmethod
    def create_anchor(
        db: Session,
        *,
        case_id: int,
        provider: BlockchainProvider | None = None,
        reason: str | None = None,
    ) -> BlockchainAnchor:
        """Anchor a case's current, verified Phase 16 audit chain state.

        Args:
            db: Database session.
            case_id: The case to anchor. Must exist.
            provider: The `BlockchainProvider` to submit to. Defaults to
                `app.blockchain.provider.get_blockchain_provider()` (the
                configured `BLOCKCHAIN_PROVIDER`/`BLOCKCHAIN_NETWORK`
                settings) when omitted.
            reason: Optional free-text label for why this anchor was
                made (e.g. `"periodic"`, `"case_closure"`, `"manual"`) --
                supports recording more than one anchor per case (task
                Phase 17 scope section 11), each independently retained.

        Returns:
            The persisted `BlockchainAnchor`.

        Raises:
            ValueError: If `case_id` does not exist.
            ChainNotValidForAnchoringError: If the case's Phase 16 chain
                does not currently verify, or has no recorded events.
                No anchor row and no `ProcessingEvent` are written.
            BlockchainProviderNotConfiguredError: If `provider` is
                omitted and no usable provider is configured.
            AnchorSubmissionError: If the resolved provider rejects the
                submission. A `ProcessingEvent` recording the failed
                attempt is still written (task Phase 17 scope section
                25/34: provider failures are controlled, observable
                outcomes, not silent).
        """
        case = CaseManager.get_case(db, case_id)
        if case is None:
            raise ValueError(f"Case with id {case_id} not found")

        chain_result = AuditChainManager.verify_case_chain(db, case_id)
        if not chain_result.valid:
            failure = chain_result.failure
            reason_text = failure.reason.value if failure else "unknown"
            raise ChainNotValidForAnchoringError(
                f"case {case_id}'s audit chain does not currently verify "
                f"({reason_text}); refusing to anchor a chain that is not "
                "known to be valid"
            )
        if chain_result.event_count == 0:
            raise ChainNotValidForAnchoringError(
                f"case {case_id} has no recorded processing events; there is no "
                "chain state to anchor"
            )

        chain_state = BlockchainManager._recompute_chain_state(db, case_id)

        resolved_provider = provider if provider is not None else get_blockchain_provider()

        try:
            submission = resolved_provider.create_anchor(
                chain_state.anchor_hash,
                metadata={
                    "case_id": case_id,
                    "chain_id": f"case-{case_id}",
                    "event_count": chain_state.event_count,
                    "last_event_id": chain_state.last_event_id,
                },
            )
        except AnchorSubmissionError as exc:
            BlockchainManager._record_anchor_event(
                db,
                case_id=case_id,
                provider_name=resolved_provider.provider_name,
                anchor_hash=chain_state.anchor_hash,
                transaction_reference=None,
                status=JobStatus.FAILED,
                error=str(exc),
            )
            raise

        anchor = BlockchainAnchor(
            case_id=case_id,
            chain_id=f"case-{case_id}",
            audit_state_hash=submission.anchor_hash,
            provider=submission.provider_name,
            network=submission.network,
            transaction_reference=submission.transaction_reference,
            status=submission.status.value,
            event_count=chain_state.event_count,
            last_event_id=chain_state.last_event_id,
            reason=reason,
            error=None,
            created_at=submission.submitted_at,
        )
        db.add(anchor)
        db.commit()
        db.refresh(anchor)

        BlockchainManager._record_anchor_event(
            db,
            case_id=case_id,
            provider_name=submission.provider_name,
            anchor_hash=submission.anchor_hash,
            transaction_reference=submission.transaction_reference,
            status=JobStatus.COMPLETED,
            error=None,
        )

        return anchor

    @staticmethod
    def _record_anchor_event(
        db: Session,
        *,
        case_id: int,
        provider_name: str,
        anchor_hash: str,
        transaction_reference: str | None,
        status: JobStatus,
        error: str | None,
    ) -> None:
        """Record the anchoring operation itself as a `ProcessingEvent`
        (task Phase 17 scope section 23), reusing Phase 15's sole
        recording path -- never a second provenance mechanism. Written
        strictly after the anchor's own hash was already computed and
        (on success) persisted; see the module docstring for why this
        does not create a circular dependency."""
        ProvenanceManager.record_event(
            db,
            case_id=case_id,
            operation=ProcessingOperation.BLOCKCHAIN_ANCHOR.value,
            actor="BlockchainManager",
            actor_type=ActorType.SYSTEM,
            tool=provider_name,
            status=status,
            parameters={"anchor_hash": anchor_hash, "transaction_reference": transaction_reference},
            error=error,
            description=f"blockchain-anchored case {case_id}'s audit chain state",
        )

    # ---- Listing / lookup -------------------------------------------------

    @staticmethod
    def list_anchors(db: Session, case_id: int) -> list[BlockchainAnchor]:
        """List every anchor ever recorded for a case, oldest first.
        Never filtered down to "the latest" -- every prior anchor is
        retained (task Phase 17 scope section 11)."""
        return (
            db.query(BlockchainAnchor)
            .filter(BlockchainAnchor.case_id == case_id)
            .order_by(BlockchainAnchor.id.asc())
            .all()
        )

    @staticmethod
    def get_anchor(db: Session, anchor_id: int) -> BlockchainAnchor | None:
        """Retrieve one anchor by primary key."""
        return db.query(BlockchainAnchor).filter(BlockchainAnchor.id == anchor_id).first()

    # ---- Verifying an anchor ----------------------------------------------

    @staticmethod
    def verify_anchor(
        db: Session, *, anchor_id: int, provider: BlockchainProvider | None = None
    ) -> AnchorVerificationResult:
        """Verify a previously-recorded anchor against the case's
        current local chain state (task Phase 17 scope section 13).

        Steps: (1) recompute the case's current Phase 16 chain validity,
        (2) recompute the current local chain-state hash from actual
        event content, (3) retrieve what the provider currently reports
        for the anchor's transaction reference, (4) compare. Never
        mutates `audit_state_hash`/`transaction_reference`/`status` --
        only `verified_at` is updated, recording when this check ran.

        Args:
            db: Database session.
            anchor_id: The `BlockchainAnchor` to verify.
            provider: The provider to check against. Defaults to
                `app.blockchain.provider.get_blockchain_provider()` when
                omitted.

        Returns:
            A structured `AnchorVerificationResult`.

        Raises:
            ValueError: If `anchor_id` does not exist.
        """
        anchor = BlockchainManager.get_anchor(db, anchor_id)
        if anchor is None:
            raise ValueError(f"BlockchainAnchor with id {anchor_id} not found")

        checked_at = datetime.now(UTC)
        chain_result: ChainVerificationResult = AuditChainManager.verify_case_chain(
            db, anchor.case_id
        )

        try:
            resolved_provider = (
                provider
                if provider is not None
                else get_blockchain_provider(provider_name=anchor.provider, network=anchor.network)
            )
        except BlockchainProviderNotConfiguredError as exc:
            result = provider_unavailable_result(
                anchor_id=anchor.id,
                case_id=anchor.case_id,
                chain_result=chain_result,
                provider_name=anchor.provider,
                network=anchor.network,
                transaction_reference=anchor.transaction_reference,
                checked_at=checked_at,
                detail=str(exc),
            )
            BlockchainManager._touch_verified_at(db, anchor, checked_at)
            return result

        try:
            provider_record = resolved_provider.get_anchor(anchor.transaction_reference)
            anchored_hash: str | None = provider_record.anchor_hash
        except AnchorNotFoundError:
            anchored_hash = None
        except BlockchainProviderError as exc:
            # Provider reachable-in-principle but failed for some other
            # controlled reason (timeout, network unavailable, malformed
            # response) -- distinct from "reachable, but doesn't know
            # this transaction" (AnchorNotFoundError, handled above).
            result = provider_unavailable_result(
                anchor_id=anchor.id,
                case_id=anchor.case_id,
                chain_result=chain_result,
                provider_name=anchor.provider,
                network=anchor.network,
                transaction_reference=anchor.transaction_reference,
                checked_at=checked_at,
                detail=str(exc),
            )
            BlockchainManager._touch_verified_at(db, anchor, checked_at)
            return result

        try:
            chain_state = BlockchainManager._recompute_chain_state(
                db, anchor.case_id, up_to_event_id=anchor.last_event_id
            )
            expected_hash = chain_state.anchor_hash
        except EmptyChainStateError:
            # Every event up to anchor.last_event_id is now gone (should
            # not normally happen -- ProcessingEvent rows are never
            # deleted by ordinary
            # operation): there is no honest state to compare, so this
            # is treated as a chain-invalid condition regardless of what
            # Phase 16's own (trivially-valid-when-empty) verify_chain
            # reported.
            expected_hash = ""
            chain_result = replace(
                chain_result,
                valid=False,
                failure=ChainFailure(
                    event_id=None,
                    reason=ChainFailureReason.MISSING_EVENT,
                    detail=f"case {anchor.case_id} now has no recorded processing events",
                ),
            )

        result = compare_anchor_state(
            anchor_id=anchor.id,
            case_id=anchor.case_id,
            expected_hash=expected_hash,
            anchored_hash=anchored_hash,
            chain_result=chain_result,
            provider_name=anchor.provider,
            network=anchor.network,
            transaction_reference=anchor.transaction_reference,
            checked_at=checked_at,
        )
        BlockchainManager._touch_verified_at(db, anchor, checked_at)
        return result

    @staticmethod
    def _touch_verified_at(db: Session, anchor: BlockchainAnchor, checked_at: datetime) -> None:
        """The one deliberate, narrow exception to `BlockchainAnchor`
        being append-only after creation: `verified_at` records when
        this anchor was last checked. Never touches `audit_state_hash`/
        `transaction_reference`/`status`/`provider`/`network`."""
        anchor.verified_at = checked_at
        db.add(anchor)
        db.commit()
