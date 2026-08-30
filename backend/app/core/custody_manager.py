"""
Business logic for physical evidence chain of custody / QR handoff
(Phase 21, Part A).

DB-aware orchestration layer built on `app.security.tokens` (opaque
token generation/hashing) and `app.core.provenance_manager` (the single
existing path for recording an immutable audit event) -- mirrors every
prior phase's pure-primitive/manager split, and never builds a second
hash chain or a second event-recording mechanism.

============================================================================
CURRENT CUSTODIAN -- derived, never cached (task Phase 21 scope section 6)
============================================================================
`get_current_custodian` is a real query over `CustodyTransfer` every time
it is called: "the receiving user of the latest ACCEPTED transfer for
this evidence item, ordered by id" -- covering both the synthetic intake
row and every real handoff uniformly, with no special case.

============================================================================
IDENTITY (task Phase 21 scope section 1)
============================================================================
Every method that changes custody state takes an already-authenticated
`User` object (resolved by `app.core.auth_manager.AuthManager`/
`app.api.deps.get_current_user` from a real bearer token), never a
caller-supplied name/ID string. `initiate_handoff` independently
re-derives the current custodian from history and compares it against
the authenticated caller -- an authenticated-but-wrong user can never
initiate a transfer for evidence they do not hold.

============================================================================
CONCURRENCY (task Phase 21 scope sections 24-27)
============================================================================
Two distinct races are guarded, by two distinct mechanisms:
- Two concurrent `initiate_handoff` calls for the same evidence item
  racing to create the *second* PENDING row: blocked by the partial
  unique index on `custody_transfers(evidence_id) WHERE status =
  'PENDING'` (see `app.models.custody.CustodyTransfer.__table_args__`)
  -- a real database constraint, not merely an application-level check
  that could itself race.
- Two concurrent `accept_handoff`/`reject_handoff`/`cancel_handoff`
  calls racing to resolve the *same* PENDING row: blocked by an atomic
  conditional `UPDATE ... WHERE id = ? AND status = 'PENDING'`
  (`_atomic_transition`, below) -- whichever call's UPDATE lands second
  affects zero rows and is reported as a lost race, never silently
  overwriting the first call's result.

============================================================================
ERROR VOCABULARY
============================================================================
`ValueError` for a domain/state problem (not found, wrong state,
expired, malformed token, duplicate intake). `PermissionError` for an
identity mismatch (not the current custodian, not the intended
receiver). `app.api.routes.custody` maps these to 404/400/403 as
appropriate; this module raises no HTTP-specific type.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.audit.events import ActorType, ProcessingOperation
from app.config import get_settings
from app.core.provenance_manager import ProvenanceManager
from app.models import (
    CustodyTransfer,
    CustodyTransferStatus,
    CustodyTransferType,
    Evidence,
    JobStatus,
    User,
)
from app.security import generate_token, hash_token

__all__ = ["CustodyManager", "IssuedHandoff"]


def _utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime to timezone-aware UTC, treating a naive value
    as already-UTC (SQLite round-trips `DateTime(timezone=True)` as
    naive -- see `app.core.validation_manager._utc` for the same,
    established pattern)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


@dataclass(frozen=True)
class IssuedHandoff:
    """A freshly initiated handoff: the persisted PENDING row plus the
    one-time raw QR token (never persisted -- only its hash is)."""

    transfer: CustodyTransfer
    raw_token: str


class CustodyManager:
    """Service layer for physical custody intake, QR handoff, and history."""

    # ---- Current custodian / history (read-only, derived) ---------------

    @staticmethod
    def get_current_custodian_transfer(db: Session, evidence_id: int) -> CustodyTransfer | None:
        """The latest ACCEPTED custody transfer for this evidence item --
        `None` if the evidence has no recorded custody yet (no intake has
        been performed). This *is* the source of truth for "who currently
        holds this evidence" (task Phase 21 scope section 6) -- there is
        no separate cached field anywhere."""
        return (
            db.query(CustodyTransfer)
            .filter(
                CustodyTransfer.evidence_id == evidence_id,
                CustodyTransfer.status == CustodyTransferStatus.ACCEPTED,
            )
            .order_by(CustodyTransfer.id.desc())
            .first()
        )

    @staticmethod
    def get_current_custodian(db: Session, evidence_id: int) -> User | None:
        """The receiving user of the latest ACCEPTED custody transfer for
        this evidence item -- `None` if the evidence has no recorded
        custody yet (no intake has been performed)."""
        latest = CustodyManager.get_current_custodian_transfer(db, evidence_id)
        return latest.receiving_user if latest is not None else None

    @staticmethod
    def get_custody_history(db: Session, evidence_id: int) -> list[CustodyTransfer]:
        """Every custody transfer recorded for this evidence item, in
        chronological (recorded) order. Read-only -- never edits or
        removes a prior row."""
        return (
            db.query(CustodyTransfer)
            .filter(CustodyTransfer.evidence_id == evidence_id)
            .order_by(CustodyTransfer.id)
            .all()
        )

    @staticmethod
    def get_transfer(db: Session, transfer_id: int) -> CustodyTransfer | None:
        return db.query(CustodyTransfer).filter(CustodyTransfer.id == transfer_id).first()

    # ---- Initial intake ---------------------------------------------------

    @staticmethod
    def record_initial_custody(
        db: Session,
        *,
        evidence_id: int,
        receiving_user: User,
        location: str | None = None,
        notes: str | None = None,
    ) -> CustodyTransfer:
        """Record the first, self-contained custody event for an evidence
        item -- no prior human custodian, no QR/token step (task Phase 21
        scope section 16).

        Raises:
            ValueError: If the evidence does not exist, or if custody has
                already been recorded for it (no duplicate intake).
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if evidence is None:
            raise ValueError(f"Evidence with id {evidence_id} not found")
        if CustodyManager.get_custody_history(db, evidence_id):
            raise ValueError(f"Evidence {evidence_id} already has recorded custody history")

        now = datetime.now(UTC)
        transfer = CustodyTransfer(
            evidence_id=evidence_id,
            transfer_type=CustodyTransferType.INTAKE,
            status=CustodyTransferStatus.ACCEPTED,
            releasing_user_id=None,
            receiving_user_id=receiving_user.id,
            initiated_at=now,
            accepted_at=now,
            location=location,
            notes=notes,
        )
        db.add(transfer)
        db.flush()

        event = ProvenanceManager.record_event(
            db,
            case_id=evidence.case_id,
            evidence_id=evidence_id,
            operation=ProcessingOperation.PHYSICAL_CUSTODY_TRANSFER.value,
            actor=receiving_user.display_name,
            actor_type=ActorType.HUMAN,
            status=JobStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            description=f"Initial custody intake by {receiving_user.display_name}",
            location_reference=location,
            notes=notes,
        )
        transfer.provenance_event_id = event.id
        db.commit()
        db.refresh(transfer)
        return transfer

    # ---- Handoff lifecycle ------------------------------------------------

    @staticmethod
    def initiate_handoff(
        db: Session,
        *,
        evidence_id: int,
        initiator: User,
        receiving_user: User,
        location: str | None = None,
        notes: str | None = None,
    ) -> IssuedHandoff:
        """Start a new QR custody handoff. Only the current custodian may
        call this successfully.

        Raises:
            ValueError: If the evidence does not exist, has no recorded
                custodian yet (intake required first), already has a
                pending transfer, or if `receiving_user` is inactive or
                the same as `initiator`.
            PermissionError: If `initiator` is not the evidence's current
                custodian.
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if evidence is None:
            raise ValueError(f"Evidence with id {evidence_id} not found")

        current_custodian = CustodyManager.get_current_custodian(db, evidence_id)
        if current_custodian is None:
            raise ValueError(
                f"Evidence {evidence_id} has no recorded custodian yet -- "
                "initial custody intake is required before a handoff can be initiated"
            )
        if current_custodian.id != initiator.id:
            raise PermissionError(
                f"User {initiator.username!r} is not the current custodian of "
                f"evidence {evidence_id}"
            )
        if not receiving_user.is_active:
            raise ValueError(f"Receiving user {receiving_user.username!r} is not active")
        if receiving_user.id == initiator.id:
            raise ValueError("Cannot initiate a handoff to oneself")

        settings = get_settings()
        now = datetime.now(UTC)
        raw_token = generate_token()

        transfer = CustodyTransfer(
            evidence_id=evidence_id,
            transfer_type=CustodyTransferType.TRANSFER,
            status=CustodyTransferStatus.PENDING,
            releasing_user_id=initiator.id,
            receiving_user_id=receiving_user.id,
            token_hash=hash_token(raw_token),
            initiated_at=now,
            expires_at=now + timedelta(minutes=settings.custody_token_ttl_minutes),
            location=location,
            notes=notes,
        )
        db.add(transfer)
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            # The partial unique index (`app.models.custody.CustodyTransfer.
            # __table_args__`) is the real guarantee here -- this branch is
            # reached only if two concurrent requests both passed the
            # `get_current_custodian`/no-pending checks above before either
            # committed.
            if CustodyManager.get_pending_transfer(db, evidence_id) is not None:
                raise ValueError(
                    f"Evidence {evidence_id} already has a pending custody transfer"
                ) from exc
            raise
        db.refresh(transfer)
        return IssuedHandoff(transfer=transfer, raw_token=raw_token)

    @staticmethod
    def get_pending_transfer(db: Session, evidence_id: int) -> CustodyTransfer | None:
        """The current PENDING transfer for this evidence item, if any --
        lazily transitioning it to EXPIRED first if its token has lapsed.
        """
        pending = (
            db.query(CustodyTransfer)
            .filter(
                CustodyTransfer.evidence_id == evidence_id,
                CustodyTransfer.status == CustodyTransferStatus.PENDING,
            )
            .order_by(CustodyTransfer.id.desc())
            .first()
        )
        if pending is None:
            return None
        return CustodyManager._resolve_expiry(db, pending)

    @staticmethod
    def inspect_pending_by_token(db: Session, *, raw_token: str, viewer: User) -> CustodyTransfer:
        """Look up the PENDING transfer a QR token refers to, for display
        before an explicit accept/reject decision. Only the intended
        receiver may inspect it (task Phase 21 scope: "receiving
        authenticated user may inspect... a handoff intended for them").

        Raises:
            ValueError: If the token is unknown, or the transfer it
                refers to is no longer pending (expired/cancelled/
                already resolved).
            PermissionError: If `viewer` is not the transfer's intended
                receiver.
        """
        transfer = CustodyManager._get_transfer_by_token(db, raw_token)
        transfer = CustodyManager._resolve_expiry(db, transfer)
        if transfer.status != CustodyTransferStatus.PENDING:
            raise ValueError(f"Transfer is no longer pending (status={transfer.status.value})")
        if transfer.receiving_user_id != viewer.id:
            raise PermissionError("This handoff is not addressed to the authenticated user")
        return transfer

    @staticmethod
    def accept_handoff(db: Session, *, raw_token: str, accepting_user: User) -> CustodyTransfer:
        """Explicitly accept a pending QR handoff. Scanning alone never
        calls this -- only an explicit accept action does.

        Raises:
            ValueError: If the token is unknown, the transfer is not (or
                is no longer) pending, or a concurrent request already
                resolved it first.
            PermissionError: If `accepting_user` is not the transfer's
                intended receiver.
        """
        transfer = CustodyManager._get_transfer_by_token(db, raw_token)
        transfer = CustodyManager._resolve_expiry(db, transfer)
        if transfer.status != CustodyTransferStatus.PENDING:
            raise ValueError(f"Transfer is no longer pending (status={transfer.status.value})")
        if transfer.receiving_user_id != accepting_user.id:
            raise PermissionError("This handoff is not addressed to the authenticated user")

        now = datetime.now(UTC)
        if not CustodyManager._atomic_transition(
            db, transfer.id, CustodyTransferStatus.ACCEPTED, accepted_at=now
        ):
            raise ValueError("Transfer was resolved by a concurrent request")
        db.refresh(transfer)

        evidence = transfer.evidence
        # `releasing_user` is only nullable for INTAKE rows (see the
        # model docstring); a TRANSFER-type row reaching this point
        # always has one.
        releasing_user = transfer.releasing_user
        assert releasing_user is not None
        event = ProvenanceManager.record_event(
            db,
            case_id=evidence.case_id,
            evidence_id=transfer.evidence_id,
            operation=ProcessingOperation.PHYSICAL_CUSTODY_TRANSFER.value,
            actor=accepting_user.display_name,
            actor_type=ActorType.HUMAN,
            status=JobStatus.COMPLETED,
            started_at=_utc(transfer.initiated_at),
            completed_at=now,
            description=(
                f"Custody transferred from {releasing_user.display_name} "
                f"to {accepting_user.display_name}"
            ),
            location_reference=transfer.location,
            notes=transfer.notes,
        )
        transfer.provenance_event_id = event.id
        db.commit()
        db.refresh(transfer)
        return transfer

    @staticmethod
    def reject_handoff(db: Session, *, raw_token: str, rejecting_user: User) -> CustodyTransfer:
        """Explicitly reject a pending QR handoff (the intended receiver
        declines it). Never recorded as a completed custody event -- a
        rejection leaves the current custodian unchanged.

        Raises:
            ValueError: If the token is unknown, the transfer is not (or
                is no longer) pending, or a concurrent request already
                resolved it first.
            PermissionError: If `rejecting_user` is not the transfer's
                intended receiver.
        """
        transfer = CustodyManager._get_transfer_by_token(db, raw_token)
        transfer = CustodyManager._resolve_expiry(db, transfer)
        if transfer.status != CustodyTransferStatus.PENDING:
            raise ValueError(f"Transfer is no longer pending (status={transfer.status.value})")
        if transfer.receiving_user_id != rejecting_user.id:
            raise PermissionError("This handoff is not addressed to the authenticated user")

        if not CustodyManager._atomic_transition(db, transfer.id, CustodyTransferStatus.REJECTED):
            raise ValueError("Transfer was resolved by a concurrent request")
        db.commit()
        db.refresh(transfer)
        return transfer

    @staticmethod
    def cancel_handoff(db: Session, *, transfer_id: int, cancelling_user: User) -> CustodyTransfer:
        """Cancel a pending handoff before it is accepted/rejected. Only
        the releasing user (the one who initiated it) may cancel.

        Raises:
            ValueError: If the transfer does not exist, is not pending,
                or a concurrent request already resolved it first.
            PermissionError: If `cancelling_user` did not initiate it.
        """
        transfer = CustodyManager.get_transfer(db, transfer_id)
        if transfer is None:
            raise ValueError(f"Custody transfer with id {transfer_id} not found")
        transfer = CustodyManager._resolve_expiry(db, transfer)
        if transfer.status != CustodyTransferStatus.PENDING:
            raise ValueError(f"Transfer is no longer pending (status={transfer.status.value})")
        if transfer.releasing_user_id != cancelling_user.id:
            raise PermissionError("Only the user who initiated this handoff may cancel it")

        if not CustodyManager._atomic_transition(db, transfer.id, CustodyTransferStatus.CANCELLED):
            raise ValueError("Transfer was resolved by a concurrent request")
        db.commit()
        db.refresh(transfer)
        return transfer

    # ---- Internal helpers ---------------------------------------------------

    @staticmethod
    def _get_transfer_by_token(db: Session, raw_token: str) -> CustodyTransfer:
        if not raw_token:
            raise ValueError("Malformed or empty token")
        transfer = (
            db.query(CustodyTransfer)
            .filter(CustodyTransfer.token_hash == hash_token(raw_token))
            .first()
        )
        if transfer is None:
            raise ValueError("No custody transfer matches this token")
        return transfer

    @staticmethod
    def _resolve_expiry(db: Session, transfer: CustodyTransfer) -> CustodyTransfer:
        """If `transfer` is PENDING and its token has lapsed, atomically
        transition it to EXPIRED and return the refreshed row."""
        if transfer.status != CustodyTransferStatus.PENDING:
            return transfer
        expires_at = _utc(transfer.expires_at)
        if expires_at is None or expires_at > datetime.now(UTC):
            return transfer
        if CustodyManager._atomic_transition(db, transfer.id, CustodyTransferStatus.EXPIRED):
            db.commit()
            db.refresh(transfer)
        return transfer

    @staticmethod
    def _atomic_transition(
        db: Session,
        transfer_id: int,
        new_status: CustodyTransferStatus,
        *,
        accepted_at: datetime | None = None,
    ) -> bool:
        """Atomically move one transfer from PENDING to `new_status`.

        Uses a single conditional `UPDATE ... WHERE id = ? AND status =
        'PENDING'` rather than load-then-save, so two concurrent callers
        racing on the same row can never both "succeed" -- exactly one
        `UPDATE` affects a row; the other affects zero and is reported as
        a lost race by the caller (task Phase 21 scope: race-condition
        safety via "transactional locking or equivalent").

        Returns:
            `True` if this call won the race (exactly one row updated);
            `False` if the transfer was no longer PENDING by the time
            this ran.
        """
        values: dict[str, object] = {"status": new_status}
        if accepted_at is not None:
            values["accepted_at"] = accepted_at
        result = cast(
            "CursorResult[Any]",
            db.execute(
                update(CustodyTransfer)
                .where(
                    CustodyTransfer.id == transfer_id,
                    CustodyTransfer.status == CustodyTransferStatus.PENDING,
                )
                .values(**values)
            ),
        )
        rowcount: int = result.rowcount
        return rowcount == 1
