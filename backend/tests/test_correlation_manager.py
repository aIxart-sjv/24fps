"""Tests for app/core/correlation_manager.py (Phase 12) — DB-level
persistence of correlation candidates as `correlated_event` `TimelineEvent`
rows. Uses synthetic multi-"camera" `TimelineEvent` rows created directly
via `TimelineManager`/the ORM, since no real multi-camera evidence exists.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.case_manager import CaseManager
from app.core.correlation_manager import CorrelationManager
from app.core.timeline_manager import TimelineManager
from app.models import Case, TimelineEvent
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base
from app.timeline.correlation import CameraTopology, CorrelationStatus


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


def _make_case(db, case_id: str = "CASE-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Test case"))


def _marker(db, case: Case, camera_id: str, timestamp: datetime) -> TimelineEvent:
    return TimelineManager.create_examiner_marker(
        db,
        case_id=case.id,
        camera_id=camera_id,
        recording_id=None,
        timestamp=timestamp,
        description=f"event on {camera_id}",
    )


def test_run_correlation_persists_a_b_c_candidate(db) -> None:
    case = _make_case(db)
    a = _marker(db, case, "A", datetime(2026, 8, 30, 10, 0, 12, tzinfo=UTC))
    b = _marker(db, case, "B", datetime(2026, 8, 30, 10, 0, 19, tzinfo=UTC))
    c = _marker(db, case, "C", datetime(2026, 8, 30, 10, 0, 31, tzinfo=UTC))
    topology = CameraTopology(transitions={("A", "B"): None, ("B", "C"): None})

    result, persisted = CorrelationManager.run_correlation(db, case.id, topology=topology)

    assert len(persisted) == 1
    correlation_event = persisted[0]
    assert correlation_event.event_type == "correlated_event"
    assert correlation_event.case_id == case.id
    assert correlation_event.source == "correlation_engine"

    # Traceability: constituent events are linked back via correlation_id.
    db.refresh(a)
    db.refresh(b)
    db.refresh(c)
    assert a.correlation_id == correlation_event.id
    assert b.correlation_id == correlation_event.id
    assert c.correlation_id == correlation_event.id

    details = json.loads(correlation_event.description)
    assert details["event_ids"] == [str(a.id), str(b.id), str(c.id)]
    assert details["status"] == CorrelationStatus.CORRELATED_CANDIDATE.value
    assert details["max_gap_seconds"] == result.max_gap_seconds


def test_run_correlation_records_effective_threshold(db) -> None:
    case = _make_case(db)
    _marker(db, case, "A", datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC))
    _marker(db, case, "B", datetime(2026, 8, 30, 10, 0, 5, tzinfo=UTC))

    result, persisted = CorrelationManager.run_correlation(db, case.id, max_gap_seconds=30.0)

    assert result.max_gap_seconds == 30.0
    details = json.loads(persisted[0].description)
    assert details["max_gap_seconds"] == 30.0


def test_run_correlation_out_of_window_events_are_not_persisted(db) -> None:
    case = _make_case(db)
    _marker(db, case, "A", datetime(2026, 8, 30, 10, 0, 12, tzinfo=UTC))
    _marker(db, case, "D", datetime(2026, 8, 30, 10, 10, 0, tzinfo=UTC))

    result, persisted = CorrelationManager.run_correlation(db, case.id)

    assert persisted == []
    assert result.candidates == []
    assert CorrelationManager.list_correlations(db, case.id) == []


def test_run_correlation_preserves_recovery_status(db) -> None:
    case = _make_case(db)
    a = _marker(db, case, "A", datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC))
    a.recovery_status = "partial"
    db.add(a)
    db.commit()
    _marker(db, case, "B", datetime(2026, 8, 30, 10, 0, 5, tzinfo=UTC))

    _, persisted = CorrelationManager.run_correlation(db, case.id)

    assert persisted[0].recovery_status == "partial"
    details = json.loads(persisted[0].description)
    assert details["recovery_signals"][str(a.id)] == "partial"


def test_run_correlation_camera_incompatible_topology_yields_no_candidate(db) -> None:
    case = _make_case(db)
    _marker(db, case, "A", datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC))
    _marker(db, case, "B", datetime(2026, 8, 30, 10, 0, 5, tzinfo=UTC))
    topology = CameraTopology(transitions={("X", "Y"): None})

    result, persisted = CorrelationManager.run_correlation(db, case.id, topology=topology)

    assert persisted == []
    assert result.candidates == []


def test_list_correlations_returns_only_persisted_correlated_events(db) -> None:
    case = _make_case(db)
    _marker(db, case, "A", datetime(2026, 8, 30, 10, 0, 12, tzinfo=UTC))
    _marker(db, case, "B", datetime(2026, 8, 30, 10, 0, 19, tzinfo=UTC))
    topology = CameraTopology(transitions={("A", "B"): None})
    CorrelationManager.run_correlation(db, case.id, topology=topology)

    correlations = CorrelationManager.list_correlations(db, case.id)

    assert len(correlations) == 1
    assert correlations[0].event_type == "correlated_event"

    # Source events themselves are not returned by list_case_events'
    # default (non-correlated) view.
    source_events = TimelineManager.list_case_events(db, case.id)
    assert all(e.event_type != "correlated_event" for e in source_events)


def test_run_correlation_is_case_scoped(db) -> None:
    case_a = _make_case(db, case_id="CASE-A")
    case_b = _make_case(db, case_id="CASE-B")
    _marker(db, case_a, "A", datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC))
    _marker(db, case_a, "B", datetime(2026, 8, 30, 10, 0, 5, tzinfo=UTC))
    _marker(db, case_b, "A", datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC))

    result_a, persisted_a = CorrelationManager.run_correlation(db, case_a.id)
    result_b, persisted_b = CorrelationManager.run_correlation(db, case_b.id)

    assert len(persisted_a) == 1
    assert persisted_b == []
    assert CorrelationManager.list_correlations(db, case_b.id) == []
