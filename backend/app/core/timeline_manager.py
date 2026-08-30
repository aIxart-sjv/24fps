"""
Business logic for timeline-event ingestion (Phase 12).

This is the DB-aware layer that materializes `TimelineEvent` rows —
`app.timeline.correlation`'s "normalized events" input — from what Phase 9
(`Recording`) and Phase 11 (`start_normalized`/`end_normalized`) already
computed. It never rescans evidence and never recomputes/reinterprets a
timestamp: `Recording.start_original/end_original/start_normalized/
end_normalized` are read exactly as Phase 8/9/11 left them.

Mirrors `app.core.recording_manager.RecordingManager`'s established
upsert-by-key idempotency pattern (`_set_metadata`) so re-ingesting the
same recording updates its existing events rather than duplicating them.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Recording, TimelineEvent

__all__ = ["TimelineManager"]

#: `TimelineEvent.event_type` values this manager produces directly
#: (Master Specification Section 28's own vocabulary).
RECORDING_START_EVENT = "recording_start"
RECORDING_END_EVENT = "recording_end"
EXAMINER_MARKER_EVENT = "examiner_marker"
CORRELATED_EVENT = "correlated_event"


class TimelineManager:
    """Service layer for ingesting and listing timeline events."""

    @staticmethod
    def ingest_recording_events(db: Session, recording_id: int) -> list[TimelineEvent]:
        """Create/update `recording_start`/`recording_end` events from one `Recording`.

        Idempotent: safe to call more than once for the same recording
        (e.g. after `TimestampManager.normalize_recording` re-runs and
        changes `start_normalized`/`end_normalized`) — updates the
        existing pair of events rather than duplicating them.

        Args:
            db: Database session.
            recording_id: Primary key of the `Recording` to ingest.

        Returns:
            `[recording_start_event, recording_end_event]`.

        Raises:
            ValueError: If the recording is not found.
        """
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            raise ValueError(f"Recording with id {recording_id} not found")

        case_id = recording.evidence.case_id
        # `Recording.camera_id` (a real per-camera identifier) takes
        # precedence when set; CP Plus never populates it (Phase 8: no
        # channel/camera-ID field located in the container bytes), so the
        # filename-derived `channel` number is the best available camera
        # identity for that vendor today — never fabricated, just the
        # next-best already-validated field.
        camera_id = (
            recording.camera_id
            if recording.camera_id is not None
            else (str(recording.channel) if recording.channel is not None else None)
        )

        start_event = TimelineManager._upsert_event(
            db,
            case_id=case_id,
            recording_id=recording.id,
            camera_id=camera_id,
            event_type=RECORDING_START_EVENT,
            original_timestamp=recording.start_original,
            normalized_timestamp=recording.start_normalized,
            source="recording_metadata",
            recovery_status=recording.recovery_status,
        )
        end_event = TimelineManager._upsert_event(
            db,
            case_id=case_id,
            recording_id=recording.id,
            camera_id=camera_id,
            event_type=RECORDING_END_EVENT,
            original_timestamp=recording.end_original,
            normalized_timestamp=recording.end_normalized,
            source="recording_metadata",
            recovery_status=recording.recovery_status,
        )
        return [start_event, end_event]

    @staticmethod
    def create_examiner_marker(
        db: Session,
        *,
        case_id: int,
        camera_id: str | None,
        recording_id: int | None,
        timestamp: datetime,
        description: str,
    ) -> TimelineEvent:
        """Record an examiner-entered or shared external event marker.

        Kept explicitly identified as manual/external (`source="examiner"`)
        — never presented as a device/vendor timestamp. Stored as both
        `original_timestamp` and `normalized_timestamp`: unlike a vendor
        clock, there is no separate device-clock-offset question for a
        timestamp the examiner states directly, so it participates in
        temporal correlation as-is (Master Specification Section 29 lists
        "shared event markers" as a direct correlation input).

        Args:
            db: Database session.
            case_id: Primary key of the owning case.
            camera_id: Camera this marker relates to, if any.
            recording_id: Recording this marker relates to, if any.
            timestamp: The examiner-supplied timestamp.
            description: What the marker records.

        Returns:
            The created `TimelineEvent`.
        """
        event = TimelineEvent(
            case_id=case_id,
            recording_id=recording_id,
            camera_id=camera_id,
            event_type=EXAMINER_MARKER_EVENT,
            original_timestamp=timestamp,
            normalized_timestamp=timestamp,
            source="examiner",
            description=description,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def list_case_events(
        db: Session, case_id: int, *, include_correlated: bool = False
    ) -> list[TimelineEvent]:
        """List a case's timeline events, ordered by primary key (insertion order).

        Args:
            db: Database session.
            case_id: Primary key of the case.
            include_correlated: When `False` (the default), excludes
                previously-persisted `correlated_event` rows — the normal
                case for feeding events *into* a fresh correlation run.

        Returns:
            The matching `TimelineEvent` rows.
        """
        query = db.query(TimelineEvent).filter(TimelineEvent.case_id == case_id)
        if not include_correlated:
            query = query.filter(TimelineEvent.event_type != CORRELATED_EVENT)
        return query.order_by(TimelineEvent.id).all()

    @staticmethod
    def _upsert_event(
        db: Session,
        *,
        case_id: int,
        recording_id: int | None,
        camera_id: str | None,
        event_type: str,
        original_timestamp: datetime | None,
        normalized_timestamp: datetime | None,
        source: str | None,
        recovery_status: str | None,
    ) -> TimelineEvent:
        """Idempotent upsert by `(case_id, recording_id, event_type)`."""
        event = (
            db.query(TimelineEvent)
            .filter(
                TimelineEvent.case_id == case_id,
                TimelineEvent.recording_id == recording_id,
                TimelineEvent.event_type == event_type,
            )
            .first()
        )
        if event is None:
            event = TimelineEvent(case_id=case_id, recording_id=recording_id, event_type=event_type)
            db.add(event)
        event.camera_id = camera_id
        event.original_timestamp = original_timestamp
        event.normalized_timestamp = normalized_timestamp
        event.source = source
        event.recovery_status = recovery_status
        db.commit()
        db.refresh(event)
        return event
