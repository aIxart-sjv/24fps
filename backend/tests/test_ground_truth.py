"""Tests for app/core/validation_manager.py's ground-truth methods
(Phase 14) -- creation, listing by dataset, and independence from AI
output (task Phase 14 scope section 4: ground truth must not simply copy
AI output)."""

from __future__ import annotations

import inspect

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.types import BoundingBox
from app.core.case_manager import CaseManager
from app.core.validation_manager import ValidationManager
from app.models import Case
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


def _make_case(db, case_id: str = "CASE-GT-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Ground truth test"))


def test_create_ground_truth_persists_all_fields(db) -> None:
    case = _make_case(db)

    row = ValidationManager.create_ground_truth(
        db,
        case_id=case.id,
        dataset_id="DS-1",
        event_type="object_detection",
        object_class="person",
        frame_number=5,
        bbox=BoundingBox(0, 0, 10, 10),
        source_reference="controlled test scenario",
        notes="synthetic person box",
    )

    assert row.id is not None
    assert row.dataset_id == "DS-1"
    assert row.event_type == "object_detection"
    assert row.object_class == "person"
    assert row.frame_number == 5
    assert row.bbox_x_min == 0
    assert row.bbox_x_max == 10
    assert row.source_reference == "controlled test scenario"


def test_list_ground_truth_scoped_to_dataset(db) -> None:
    case = _make_case(db)
    ValidationManager.create_ground_truth(
        db, case_id=case.id, dataset_id="DS-A", event_type="motion", source_reference="a"
    )
    ValidationManager.create_ground_truth(
        db, case_id=case.id, dataset_id="DS-B", event_type="motion", source_reference="b"
    )

    rows_a = ValidationManager.list_ground_truth(db, case.id, "DS-A")
    rows_b = ValidationManager.list_ground_truth(db, case.id, "DS-B")

    assert len(rows_a) == 1
    assert len(rows_b) == 1
    assert rows_a[0].dataset_id == "DS-A"


def test_list_ground_truth_filters_by_event_type(db) -> None:
    case = _make_case(db)
    ValidationManager.create_ground_truth(
        db, case_id=case.id, dataset_id="DS-1", event_type="object_detection", source_reference="x"
    )
    ValidationManager.create_ground_truth(
        db, case_id=case.id, dataset_id="DS-1", event_type="motion", source_reference="x"
    )

    detection_only = ValidationManager.list_ground_truth(
        db, case.id, "DS-1", event_type="object_detection"
    )

    assert len(detection_only) == 1
    assert detection_only[0].event_type == "object_detection"


def test_ground_truth_is_scoped_to_case(db) -> None:
    case_a = _make_case(db, case_id="CASE-GT-A")
    case_b = _make_case(db, case_id="CASE-GT-B")
    ValidationManager.create_ground_truth(
        db, case_id=case_a.id, dataset_id="DS-SHARED", event_type="motion", source_reference="a"
    )

    rows_a = ValidationManager.list_ground_truth(db, case_a.id, "DS-SHARED")
    rows_b = ValidationManager.list_ground_truth(db, case_b.id, "DS-SHARED")

    assert len(rows_a) == 1
    assert len(rows_b) == 0


def test_create_ground_truth_never_reads_from_an_ai_output_table(db) -> None:
    """Structural guarantee, not just a behavioral one: `create_ground_truth`'s
    source code never references any AI-output model, so ground truth
    cannot be silently copied from a system result."""
    source = inspect.getsource(ValidationManager.create_ground_truth)
    for forbidden in ("AIResult", "AITrack", "MotionEvent", "TimelineEvent", "RecoveryResult"):
        assert forbidden not in source
