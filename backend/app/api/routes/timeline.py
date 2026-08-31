"""
API route for reading a case's canonical timeline (Phase 12, "Canonical
Timeline"). Master Specification Section 46 (API Design) lists
`GET timeline` under the `TIMELINE` section; this is that read route.

Phase 22 gap assessment (frontend/backend integration audit): no route
exposed `app.core.timeline_manager.TimelineManager.list_case_events` at
all -- only correlation *results* were readable
(`GET /cases/{case_id}/correlation/events`), never the raw source events
(`recording_start`/`recording_end`/`examiner_marker`) those results were
computed from. The officer-facing timeline view needs the raw events
too, so this route fills that gap. It never recomputes or reinterprets a
timestamp -- purely a read of already-persisted `TimelineEvent` rows.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_case_access
from app.core.timeline_manager import TimelineManager
from app.models import Case, RecordingMetadata, TimelineEvent
from app.schemas.timeline import TimelineEventResponse
from app.storage.db import get_db

router = APIRouter()

#: `RecordingMetadata.key`s `app.core.timestamp_manager.TimestampManager`
#: writes -- read here (never recomputed) to answer Phase 24 task scope,
#: "Timeline": "Original timestamp, Normalized timestamp, Timestamp
#: status, Source, Timezone status".
_TIMESTAMP_STATUS_KEY = "timestamp_normalization_status"
_TIMESTAMP_SOURCE_KEY = "timestamp_normalization_source"
_TIMEZONE_KEY = "timestamp_source_timezone"
_TIMEZONE_BASIS_KEY = "timestamp_source_timezone_basis"
_TIMESTAMP_METADATA_KEYS = {
    _TIMESTAMP_STATUS_KEY,
    _TIMESTAMP_SOURCE_KEY,
    _TIMEZONE_KEY,
    _TIMEZONE_BASIS_KEY,
}


def _event_response(db: Session, event: TimelineEvent) -> TimelineEventResponse:
    metadata: dict[str, str | None] = {}
    if event.recording_id is not None:
        rows = (
            db.query(RecordingMetadata)
            .filter(
                RecordingMetadata.recording_id == event.recording_id,
                RecordingMetadata.key.in_(_TIMESTAMP_METADATA_KEYS),
            )
            .all()
        )
        metadata = {row.key: row.value for row in rows}

    return TimelineEventResponse(
        id=event.id,
        case_id=event.case_id,
        recording_id=event.recording_id,
        camera_id=event.camera_id,
        event_type=event.event_type,
        original_timestamp=event.original_timestamp,
        normalized_timestamp=event.normalized_timestamp,
        confidence=event.confidence,
        source=event.source,
        description=event.description,
        ai_reference=event.ai_reference,
        recovery_status=event.recovery_status,
        correlation_id=event.correlation_id,
        created_at=event.created_at,
        timestamp_status=metadata.get(_TIMESTAMP_STATUS_KEY) or "unknown",
        timestamp_source=metadata.get(_TIMESTAMP_SOURCE_KEY),
        timezone_status="known" if metadata.get(_TIMEZONE_KEY) else "unknown",
        timezone_basis=metadata.get(_TIMEZONE_BASIS_KEY),
    )


@router.get("/cases/{case_id}/timeline", response_model=list[TimelineEventResponse])
def list_case_timeline(
    case_id: int,
    include_correlated: bool = False,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[TimelineEventResponse]:
    """List a case's canonical timeline events, in insertion order.

    Args:
        case_id: The case to list events for. Must exist.
        include_correlated: When `True`, also includes previously
            persisted `correlated_event` rows (available in full detail
            via `GET /cases/{case_id}/correlation/events` instead).
            Defaults to `False`.
    """
    del case
    events = TimelineManager.list_case_events(db, case_id, include_correlated=include_correlated)
    return [_event_response(db, e) for e in events]
