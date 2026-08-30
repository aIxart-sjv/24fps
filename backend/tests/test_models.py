"""
Tests for ORM models.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Case, CaseStatus, Device, Evidence, Recording, Storage


def test_case_creation(test_db):
    """Test creating a Case."""
    case = Case(
        case_id="TEST-2026-001",
        name="Test Case",
        examiner="John Doe",
        status=CaseStatus.DRAFT,
    )
    test_db.add(case)
    test_db.commit()

    retrieved = test_db.query(Case).filter(Case.case_id == "TEST-2026-001").first()
    assert retrieved is not None
    assert retrieved.name == "Test Case"
    assert retrieved.examiner == "John Doe"
    assert retrieved.status == CaseStatus.DRAFT


def test_evidence_creation(test_db):
    """Test creating Evidence."""
    case = Case(case_id="TEST-2026-002", name="Test Case 2", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(
        evidence_id="E001",
        case_id=case.id,
        source_type="forensic_image",
        source_path="/path/to/image.dd",
    )
    test_db.add(evidence)
    test_db.commit()

    retrieved = test_db.query(Evidence).filter(Evidence.evidence_id == "E001").first()
    assert retrieved is not None
    assert retrieved.source_type == "forensic_image"
    assert retrieved.case_id == case.id


def test_device_creation(test_db):
    """Test creating Device."""
    case = Case(case_id="TEST-2026-003", name="Test Case 3", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(
        evidence_id="E002",
        case_id=case.id,
        source_type="forensic_image",
    )
    test_db.add(evidence)
    test_db.commit()

    device = Device(
        evidence_id=evidence.id,
        vendor="CP Plus",
        model="DVXVR",
        firmware="3.1.0",
    )
    test_db.add(device)
    test_db.commit()

    retrieved = test_db.query(Device).filter(Device.evidence_id == evidence.id).first()
    assert retrieved is not None
    assert retrieved.vendor == "CP Plus"


def test_storage_creation(test_db):
    """Test creating Storage."""
    case = Case(case_id="TEST-2026-004", name="Test Case 4", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(
        evidence_id="E003",
        case_id=case.id,
        source_type="forensic_image",
    )
    test_db.add(evidence)
    test_db.commit()

    storage = Storage(
        evidence_id=evidence.id,
        manufacturer="Seagate",
        capacity_bytes=2000000000000,
        sector_size=512,
    )
    test_db.add(storage)
    test_db.commit()

    retrieved = test_db.query(Storage).filter(Storage.evidence_id == evidence.id).first()
    assert retrieved is not None
    assert retrieved.manufacturer == "Seagate"
    assert retrieved.capacity_bytes == 2000000000000


def test_recording_creation(test_db):
    """Test creating Recording."""
    case = Case(case_id="TEST-2026-005", name="Test Case 5", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(
        evidence_id="E004",
        case_id=case.id,
        source_type="forensic_image",
    )
    test_db.add(evidence)
    test_db.commit()

    now = datetime.now(UTC)
    recording = Recording(
        evidence_id=evidence.id,
        recording_id="REC-001",
        camera_id="CAM-01",
        channel=1,
        start_original=now,
        codec="H.264",
    )
    test_db.add(recording)
    test_db.commit()

    retrieved = test_db.query(Recording).filter(Recording.recording_id == "REC-001").first()
    assert retrieved is not None
    assert retrieved.camera_id == "CAM-01"
    assert retrieved.codec == "H.264"


def test_case_evidence_relationship(test_db):
    """Test Case -> Evidence relationship."""
    case = Case(case_id="TEST-2026-006", name="Test Case 6", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence1 = Evidence(evidence_id="E005", case_id=case.id, source_type="forensic_image")
    evidence2 = Evidence(evidence_id="E006", case_id=case.id, source_type="native_export")
    test_db.add_all([evidence1, evidence2])
    test_db.commit()

    retrieved_case = test_db.query(Case).filter(Case.case_id == "TEST-2026-006").first()
    evidence_count = test_db.query(Evidence).filter(Evidence.case_id == retrieved_case.id).count()
    assert evidence_count == 2


def test_case_optional_fields_default_to_none(test_db):
    """Test that Case optional fields are None when not provided."""
    case = Case(case_id="TEST-2026-007", name="Minimal Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()
    test_db.refresh(case)

    assert case.case_number is None
    assert case.description is None
    assert case.examiner is None
    assert case.reference_time is None
    assert case.software_version is None


def test_evidence_optional_relationships_default_to_none(test_db):
    """Test that Evidence.device and Evidence.storage are None until registered."""
    case = Case(case_id="TEST-2026-008", name="Relationship Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(evidence_id="E007", case_id=case.id, source_type="forensic_image")
    test_db.add(evidence)
    test_db.commit()
    test_db.refresh(evidence)

    assert evidence.device is None
    assert evidence.storage is None
    assert evidence.case.id == case.id


def test_evidence_device_relationship_populated(test_db):
    """Test that Evidence.device resolves to the linked Device once created."""
    case = Case(case_id="TEST-2026-009", name="Device Relationship Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(evidence_id="E008", case_id=case.id, source_type="forensic_image")
    test_db.add(evidence)
    test_db.commit()

    device = Device(evidence_id=evidence.id, vendor="Hikvision")
    test_db.add(device)
    test_db.commit()
    test_db.refresh(evidence)

    assert evidence.device is not None
    assert evidence.device.vendor == "Hikvision"


def test_deleting_case_with_evidence_is_blocked_not_cascaded(test_db):
    """Deleting a Case with Evidence must fail rather than silently destroy evidence.

    With no delete cascade and evidence.case_id NOT NULL, SQLAlchemy's
    unit-of-work refuses to detach or delete the related Evidence rows,
    so the deletion raises instead of quietly losing forensic evidence.
    """
    case = Case(case_id="TEST-2026-010", name="Cascade Test Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(evidence_id="E009", case_id=case.id, source_type="forensic_image")
    test_db.add(evidence)
    test_db.commit()
    evidence_pk = evidence.id
    case_pk = case.id

    test_db.delete(case)
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()

    surviving_evidence = test_db.query(Evidence).filter(Evidence.id == evidence_pk).first()
    assert surviving_evidence is not None
    assert surviving_evidence.evidence_id == "E009"

    surviving_case = test_db.query(Case).filter(Case.id == case_pk).first()
    assert surviving_case is not None
