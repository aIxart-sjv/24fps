"""
Business logic for running and persisting cross-camera correlation
(Phase 12). Loads a case's timeline events, delegates the actual
correlation judgment entirely to the pure engine in
`app.timeline.correlation`, and persists each candidate as one
`event_type="correlated_event"` `TimelineEvent` row.

Never computes a signal itself and never overwrites a source event: a
`correlated_event` row only ever gains a `correlation_id` link from its
constituent source events (mirroring `Artifact.parent_artifact_id`,
Phase 4) — original/normalized timestamps, camera IDs, recording IDs, and
recovery status on the source rows are untouched.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.timeline_manager import CORRELATED_EVENT, TimelineManager
from app.models import TimelineEvent
from app.timeline.correlation import (
    DEFAULT_MAX_GAP_SECONDS,
    CameraTopology,
    CorrelationCandidate,
    CorrelationInputEvent,
    CorrelationRunResult,
    RecoverySignal,
    correlate,
)

__all__ = ["CorrelationManager"]

#: Aggregate-worst ordering for a candidate's `recovery_signals` map, used
#: to pick one representative `TimelineEvent.recovery_status` string for
#: the persisted `correlated_event` row (Master Specification Section 24:
#: incompleteness must never be hidden by an optimistic default).
_RECOVERY_WORST_FIRST = [RecoverySignal.UNKNOWN, RecoverySignal.PARTIAL, RecoverySignal.FULL]


class CorrelationManager:
    """Service layer for running cross-camera correlation over a case."""

    @staticmethod
    def run_correlation(
        db: Session,
        case_id: int,
        *,
        topology: CameraTopology | None = None,
        max_gap_seconds: float | None = None,
    ) -> tuple[CorrelationRunResult, list[TimelineEvent]]:
        """Run correlation over a case's current source events and persist the results.

        Args:
            db: Database session.
            case_id: Primary key of the case.
            topology: Explicit, examiner-configured camera adjacency, or
                `None` (reported as unavailable — never inferred).
            max_gap_seconds: Effective temporal window; `None` uses
                `DEFAULT_MAX_GAP_SECONDS`.

        Returns:
            `(result, persisted_correlation_events)` — `result` is the
            full engine output (including the processing summary);
            `persisted_correlation_events` are the newly created
            `correlated_event` rows, one per candidate.
        """
        source_events = TimelineManager.list_case_events(db, case_id, include_correlated=False)
        input_events = [CorrelationManager._to_input_event(event) for event in source_events]
        effective_gap = max_gap_seconds if max_gap_seconds is not None else DEFAULT_MAX_GAP_SECONDS

        result = correlate(input_events, topology=topology, max_gap_seconds=effective_gap)

        events_by_id = {str(event.id): event for event in source_events}
        persisted = [
            CorrelationManager._persist_candidate(db, case_id, candidate, events_by_id)
            for candidate in result.candidates
        ]
        return result, persisted

    @staticmethod
    def list_correlations(db: Session, case_id: int) -> list[TimelineEvent]:
        """List previously persisted `correlated_event` rows for a case.

        Args:
            db: Database session.
            case_id: Primary key of the case.

        Returns:
            The matching `TimelineEvent` rows, each with its constituent
            source events reachable via `source_events`.
        """
        return (
            db.query(TimelineEvent)
            .filter(TimelineEvent.case_id == case_id, TimelineEvent.event_type == CORRELATED_EVENT)
            .order_by(TimelineEvent.id)
            .all()
        )

    @staticmethod
    def _to_input_event(event: TimelineEvent) -> CorrelationInputEvent:
        """Convert a persisted source `TimelineEvent` into the engine's plain input type.

        `track_reference`/`movement` are always `None`: no object-
        detection/tracking subsystem exists yet to populate them (Phase 13
        territory) — never fabricated here.
        """
        return CorrelationInputEvent(
            event_id=str(event.id),
            case_id=str(event.case_id),
            camera_id=event.camera_id,
            recording_id=str(event.recording_id) if event.recording_id is not None else None,
            event_type=event.event_type,
            original_timestamp=event.original_timestamp,
            normalized_timestamp=event.normalized_timestamp,
            recovery_status=event.recovery_status,
            is_examiner_marker=event.event_type == "examiner_marker",
        )

    @staticmethod
    def _persist_candidate(
        db: Session,
        case_id: int,
        candidate: CorrelationCandidate,
        events_by_id: dict[str, TimelineEvent],
    ) -> TimelineEvent:
        """Persist one candidate as a `correlated_event` row linked to its source events.

        No single camera/recording/timestamp represents a multi-camera
        candidate, so `camera_id`/`recording_id`/`original_timestamp` stay
        `None` on this row — never an arbitrarily picked member. The
        earliest constituent `normalized_timestamp` (all candidates have
        at least one, since the engine only chains events that already
        have one) anchors this row chronologically for listing/sorting.
        The full structured signal breakdown (per-link temporal/topology/
        movement/track signals, reasons, warnings, method, effective
        threshold) is JSON-encoded into `description` — mirroring the
        existing `RecordingMetadata` convention (Phase 9) of JSON-encoding
        structured values into a free-text field rather than adding
        dedicated columns for data that has no other consumer.
        """
        members = [events_by_id[event_id] for event_id in candidate.event_ids]
        normalized_timestamps = [
            member.normalized_timestamp
            for member in members
            if member.normalized_timestamp is not None
        ]
        earliest_normalized = min(normalized_timestamps) if normalized_timestamps else None

        recovery_values = set(candidate.recovery_signals.values())
        overall_recovery = next(
            (signal for signal in _RECOVERY_WORST_FIRST if signal in recovery_values),
            RecoverySignal.UNKNOWN,
        ).value

        details = {
            "status": candidate.status.value,
            "method": candidate.method,
            "max_gap_seconds": candidate.max_gap_seconds,
            "event_ids": candidate.event_ids,
            "confidence_basis": candidate.confidence_basis,
            "warnings": candidate.warnings,
            "recovery_signals": {k: v.value for k, v in candidate.recovery_signals.items()},
            "links": [
                {
                    "from_event_id": link.from_event_id,
                    "to_event_id": link.to_event_id,
                    "status": link.status.value,
                    "temporal": link.signals.temporal.value,
                    "topology": link.signals.topology.value,
                    "movement": link.signals.movement.value,
                    "track": link.signals.track.value,
                    "gap_seconds": link.signals.gap_seconds,
                    "confidence": link.confidence,
                    "confidence_basis": link.confidence_basis,
                    "reasons": link.reasons,
                    "warnings": link.warnings,
                }
                for link in candidate.links
            ],
        }

        correlation_event = TimelineEvent(
            case_id=case_id,
            recording_id=None,
            camera_id=None,
            event_type=CORRELATED_EVENT,
            original_timestamp=None,
            normalized_timestamp=earliest_normalized,
            confidence=candidate.confidence,
            source="correlation_engine",
            description=json.dumps(details),
            ai_reference=None,
            recovery_status=overall_recovery,
        )
        db.add(correlation_event)
        db.commit()
        db.refresh(correlation_event)

        for member in members:
            member.correlation_id = correlation_event.id
            db.add(member)
        db.commit()
        db.refresh(correlation_event)

        return correlation_event
