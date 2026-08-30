"""
Business logic for the hash-linked audit chain (Phase 16).
Master Specification Section 41 ("Hash-Linked Audit Log").

This is the DB-aware orchestration layer built on `app.audit.hash_chain`
(the pure canonicalization/hashing/verification engine):
`ProvenanceManager.record_event` (Phase 15) is the sole path that creates
a `ProcessingEvent`; immediately after adding it to the session, it calls
`AuditChainManager.seal_event` here to compute and assign that event's
`previous_hash`/`current_hash` before the row is ever committed --
exactly one INSERT per event, always fully sealed. This module never
creates a `ProcessingEvent` itself (no competing event-recording path)
and never updates a previously-sealed row.
"""

from __future__ import annotations

import dataclasses
import json

from sqlalchemy.orm import Session

from app.audit.hash_chain import (
    CHAIN_SCOPE,
    GENESIS_PREVIOUS_HASH,
    ChainableEvent,
    ChainLink,
    ChainVerificationResult,
    compute_event_hash,
    verify_chain,
)
from app.models import ProcessingEvent

__all__ = ["AuditChainManager"]


def _to_chainable(event: ProcessingEvent) -> ChainableEvent:
    """Convert a persisted `ProcessingEvent` row into the plain,
    DB-free dataclass `app.audit.hash_chain` operates on, decoding its
    JSON-encoded columns back into the exact Python values that were
    originally hashed."""
    return ChainableEvent(
        id=event.id,
        case_id=event.case_id,
        evidence_id=event.evidence_id,
        job_id=event.job_id,
        operation=event.operation,
        actor=event.actor,
        actor_type=event.actor_type,
        tool=event.tool,
        tool_version=event.tool_version,
        software_version=event.software_version,
        parameters=json.loads(event.parameters) if event.parameters else None,
        input_artifact_ids=(
            json.loads(event.input_artifact_ids) if event.input_artifact_ids else None
        ),
        output_artifact_ids=(
            json.loads(event.output_artifact_ids) if event.output_artifact_ids else None
        ),
        started_at=event.started_at,
        completed_at=event.completed_at,
        status=event.status,
        warnings=json.loads(event.warnings) if event.warnings else None,
        error=event.error,
        notes=event.notes,
        description=event.description,
        location_reference=event.location_reference,
    )


class AuditChainManager:
    """Service layer for sealing new events into, and verifying, the
    per-case hash-linked audit chain."""

    @staticmethod
    def seal_event(db: Session, event: ProcessingEvent) -> ProcessingEvent:
        """Assign a newly-created event's position in its case's hash chain.

        Not a general-purpose event-creation path: callers create events
        through `app.core.provenance_manager.ProvenanceManager.
        record_event`, which calls this immediately afterward. `event`
        must already be `db.add`-ed to `db` but not yet committed (no
        `id` assigned yet -- the event's own `id` is part of its hashed
        payload, so this method flushes first to obtain it).

        Args:
            db: Database session.
            event: The unsealed `ProcessingEvent`, already added to `db`.

        Returns:
            The same event, now committed with `previous_hash`/
            `current_hash` set. Exactly one row is ever visible to any
            other session, and it is always fully sealed -- this
            completes one logical append inside one transaction, it does
            not update a previously-committed row.

        Raises:
            RuntimeError: If the case's current chain tail has no
                `current_hash` of its own -- would indicate a prior
                sealing defect; never happens in normal operation, since
                every event only ever reaches this table through this
                same method.
        """
        db.flush()  # Assigns event.id (needed in the hash payload) without committing.

        tail = (
            db.query(ProcessingEvent)
            .filter(ProcessingEvent.case_id == event.case_id, ProcessingEvent.id != event.id)
            .order_by(ProcessingEvent.id.desc())
            .first()
        )
        if tail is None:
            previous_hash = GENESIS_PREVIOUS_HASH
        elif tail.current_hash is None:
            raise RuntimeError(
                f"cannot extend the hash chain for case {event.case_id}: preceding event "
                f"{tail.id} has no current_hash"
            )
        else:
            previous_hash = tail.current_hash

        current_hash = compute_event_hash(_to_chainable(event), previous_hash=previous_hash)

        event.previous_hash = previous_hash
        event.current_hash = current_hash
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def verify_case_chain(db: Session, case_id: int) -> ChainVerificationResult:
        """Verify a case's entire hash chain.

        Events are ordered by `ProcessingEvent.id` ascending -- `id` is
        guaranteed unique and strictly increasing in true insertion
        order (SQLite autoincrement), which is the reliable ordering
        signal here: `ProcessingEvent` rows can legitimately be recorded
        retroactively (Phase 15's own design has no live start/complete
        signal), so `started_at`/`completed_at` are not safe as the
        primary chain order.

        Args:
            db: Database session.
            case_id: The case whose chain to verify. Not required to
                exist -- a case with no recorded events verifies as a
                trivially valid, empty chain.

        Returns:
            A `ChainVerificationResult` with `case_id`/`chain_scope`
            filled in.
        """
        events = (
            db.query(ProcessingEvent)
            .filter(ProcessingEvent.case_id == case_id)
            .order_by(ProcessingEvent.id.asc())
            .all()
        )
        links = [
            ChainLink(
                event=_to_chainable(event),
                stored_previous_hash=event.previous_hash,
                stored_current_hash=event.current_hash,
            )
            for event in events
        ]
        result = verify_chain(links)
        return dataclasses.replace(result, case_id=case_id, chain_scope=CHAIN_SCOPE)

    @staticmethod
    def recompute_event_hash(db: Session, event_id: int) -> str:
        """Independently recompute one event's expected `current_hash`
        from its stored content and stored `previous_hash` -- a
        reproducibility check, decoupled from whatever is currently
        stored in the event's own `current_hash` column.

        Args:
            db: Database session.
            event_id: The event to recompute.

        Returns:
            The recomputed hex digest.

        Raises:
            ValueError: If the event does not exist or has no
                `previous_hash` recorded (never sealed).
        """
        event = db.query(ProcessingEvent).filter(ProcessingEvent.id == event_id).first()
        if event is None:
            raise ValueError(f"ProcessingEvent with id {event_id} not found")
        if event.previous_hash is None:
            raise ValueError(f"ProcessingEvent {event_id} has no previous_hash recorded")
        return compute_event_hash(_to_chainable(event), previous_hash=event.previous_hash)
