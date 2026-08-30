"""Tests for app/core/timeline_manager.py (Phase 12), against small
synthetic `Case`/`Evidence`/`Recording` rows created directly via the
ORM — no real evidence required.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.case_manager import CaseManager
from app.core.timeline_manager import (
    EXAMINER_MARKER_EVENT,
    RECORDING_END_EVENT,
    RECORDING_START_EVENT,
    TimelineManager,
)
from app.models import Case, Evidence, Recording
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _make_case(db: Session, case_id: str = "CASE-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Test case"))


def _make_recording(
    db: Session,
    case: Case,
    *,
    recording_id: str = "REC-1",
    camera_id: str | None = None,
    channel: int | None = 1,
    recovery_status: str | None = None,
) -> Recording:
    evidence = Evidence(evidence_id=f"EVID-{recording_id}", case_id=case.id, source_type="cp_plus")
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    recording = Recording(
        evidence_id=evidence.id,
        recording_id=recording_id,
        camera_id=camera_id,
        channel=channel,
        start_original=datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC),
        end_original=datetime(2026, 8, 28, 16, 20, 2, tzinfo=UTC),
        start_normalized=datetime(2026, 8, 28, 16, 20, 0, tzinfo=UTC),
        end_normalized=datetime(2026, 8, 28, 16, 20, 2, tzinfo=UTC),
        recovery_status=recovery_status,
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return recording


def test_ingest_recording_events_creates_start_and_end_events(db: Session) -> None:
    case = _make_case(db)
    recording = _make_recording(db, case)

    events = TimelineManager.ingest_recording_events(db, recording.id)

    assert len(events) == 2
    start, end = events
    assert start.event_type == RECORDING_START_EVENT
    assert start.normalized_timestamp == recording.start_normalized
    assert start.original_timestamp == recording.start_original
    assert end.event_type == RECORDING_END_EVENT
    assert end.normalized_timestamp == recording.end_normalized
    assert start.case_id == case.id
    assert start.recording_id == recording.id


def test_ingest_recording_events_uses_channel_as_camera_id_fallback(db: Session) -> None:
    case = _make_case(db)
    recording = _make_recording(db, case, camera_id=None, channel=3)

    events = TimelineManager.ingest_recording_events(db, recording.id)

    assert all(event.camera_id == "3" for event in events)


def test_ingest_recording_events_prefers_explicit_camera_id(db: Session) -> None:
    case = _make_case(db)
    recording = _make_recording(db, case, camera_id="entrance-cam", channel=3)

    events = TimelineManager.ingest_recording_events(db, recording.id)

    assert all(event.camera_id == "entrance-cam" for event in events)


def test_ingest_recording_events_is_idempotent(db: Session) -> None:
    case = _make_case(db)
    recording = _make_recording(db, case)

    first = TimelineManager.ingest_recording_events(db, recording.id)
    second = TimelineManager.ingest_recording_events(db, recording.id)

    assert [e.id for e in first] == [e.id for e in second]
    all_events = TimelineManager.list_case_events(db, case.id)
    assert len(all_events) == 2


def test_ingest_recording_events_reflects_updated_normalization(db: Session) -> None:
    case = _make_case(db)
    recording = _make_recording(db, case)

    TimelineManager.ingest_recording_events(db, recording.id)

    recording.start_normalized = datetime(2026, 8, 28, 17, 0, 0, tzinfo=UTC)
    db.add(recording)
    db.commit()

    events = TimelineManager.ingest_recording_events(db, recording.id)
    start = next(e for e in events if e.event_type == RECORDING_START_EVENT)
    assert start.normalized_timestamp is not None
    # SQLite round-trips DateTime(timezone=True) values as naive (an
    # established characteristic, not a Phase 12 defect) -- compare
    # component-wise rather than assuming tzinfo survives the round-trip.
    assert start.normalized_timestamp.replace(tzinfo=UTC) == datetime(
        2026, 8, 28, 17, 0, 0, tzinfo=UTC
    )


def test_ingest_recording_events_propagates_recovery_status(db: Session) -> None:
    case = _make_case(db)
    recording = _make_recording(db, case, recovery_status="partial")

    events = TimelineManager.ingest_recording_events(db, recording.id)

    assert all(event.recovery_status == "partial" for event in events)


def test_ingest_recording_events_raises_for_missing_recording(db: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        TimelineManager.ingest_recording_events(db, 999)


def test_create_examiner_marker(db: Session) -> None:
    case = _make_case(db)
    timestamp = datetime(2026, 8, 28, 16, 20, 1, tzinfo=UTC)

    marker = TimelineManager.create_examiner_marker(
        db,
        case_id=case.id,
        camera_id="entrance",
        recording_id=None,
        timestamp=timestamp,
        description="Suspect seen entering building",
    )

    assert marker.event_type == EXAMINER_MARKER_EVENT
    assert marker.source == "examiner"
    assert marker.original_timestamp is not None
    assert marker.normalized_timestamp is not None
    assert marker.original_timestamp.replace(tzinfo=UTC) == timestamp
    assert marker.normalized_timestamp.replace(tzinfo=UTC) == timestamp
    assert marker.description == "Suspect seen entering building"


def test_list_case_events_excludes_correlated_events_by_default(db: Session) -> None:
    case = _make_case(db)
    recording = _make_recording(db, case)
    TimelineManager.ingest_recording_events(db, recording.id)
    TimelineManager.create_examiner_marker(
        db,
        case_id=case.id,
        camera_id=None,
        recording_id=None,
        timestamp=datetime(2026, 8, 28, 16, 20, 1, tzinfo=UTC),
        description="marker",
    )

    events = TimelineManager.list_case_events(db, case.id)

    assert len(events) == 3
    assert all(e.event_type != "correlated_event" for e in events)


def test_list_case_events_is_scoped_to_case(db: Session) -> None:
    case_a = _make_case(db, case_id="CASE-A")
    case_b = _make_case(db, case_id="CASE-B")
    recording_a = _make_recording(db, case_a, recording_id="REC-A")
    _make_recording(db, case_b, recording_id="REC-B")
    TimelineManager.ingest_recording_events(db, recording_a.id)

    events_a = TimelineManager.list_case_events(db, case_a.id)
    events_b = TimelineManager.list_case_events(db, case_b.id)

    assert len(events_a) == 2
    assert len(events_b) == 0
