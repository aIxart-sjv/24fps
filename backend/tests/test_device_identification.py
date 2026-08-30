"""Tests for EvidenceManager.identify_device/detect_format (DB persistence)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings
from app.core.evidence_manager import EvidenceManager
from app.models import Case, CaseStatus, Device, Evidence, Storage
from app.schemas.device import IdentificationStatus


@pytest.fixture
def evidence_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.fixture
def raw_dd_evidence(test_db, evidence_root: Path) -> Evidence:
    case = Case(case_id="ID-CASE-001", name="Identification Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    image_path = evidence_root / "image.dd"
    buf = bytearray(4096)
    buf[1024 + 56 : 1024 + 58] = b"\x53\xef"  # ext magic, for a non-trivial result
    image_path.write_bytes(bytes(buf))

    evidence = Evidence(
        evidence_id="ID-E001",
        case_id=case.id,
        source_type="raw_dd",
        source_path=str(image_path.resolve()),
    )
    test_db.add(evidence)
    test_db.commit()
    return evidence


def test_identify_device_creates_device_row(test_db, raw_dd_evidence: Evidence):
    device, result = EvidenceManager.identify_device(test_db, raw_dd_evidence.id)

    assert isinstance(device, Device)
    assert device.evidence_id == raw_dd_evidence.id
    assert device.device_type == "storage_media"
    assert device.confidence == result.confidence
    assert device.identification_method == result.identification_method
    assert device.vendor is None  # never fabricated


def test_identify_device_is_idempotent_and_upserts(test_db, raw_dd_evidence: Evidence):
    device_first, _ = EvidenceManager.identify_device(test_db, raw_dd_evidence.id)
    first_id = device_first.id

    device_second, _ = EvidenceManager.identify_device(test_db, raw_dd_evidence.id)

    assert device_second.id == first_id
    rows = test_db.query(Device).filter(Device.evidence_id == raw_dd_evidence.id).all()
    assert len(rows) == 1


def test_identify_device_missing_evidence_raises(test_db):
    with pytest.raises(ValueError, match="not found"):
        EvidenceManager.identify_device(test_db, 99999)


def test_identify_device_without_source_path_raises(test_db):
    case = Case(case_id="ID-CASE-002", name="No Source", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()
    evidence = Evidence(evidence_id="ID-E002", case_id=case.id, source_type="raw_dd")
    test_db.add(evidence)
    test_db.commit()

    with pytest.raises(ValueError, match="no source_path"):
        EvidenceManager.identify_device(test_db, evidence.id)


def test_detect_format_creates_storage_row(test_db, raw_dd_evidence: Evidence):
    storage, result = EvidenceManager.detect_format(test_db, raw_dd_evidence.id)

    assert isinstance(storage, Storage)
    assert storage.evidence_id == raw_dd_evidence.id
    assert storage.sector_size == result.sector_size
    assert storage.capacity_bytes == result.capacity
    assert storage.image_format == "raw_dd"
    assert storage.image_path == raw_dd_evidence.source_path
    assert storage.read_only is True
    assert storage.status == IdentificationStatus.PARTIAL.value
    # Physical-media facts that cannot be determined from file inspection.
    assert storage.manufacturer is None
    assert storage.interface is None


def test_detect_format_is_idempotent_and_upserts(test_db, raw_dd_evidence: Evidence):
    storage_first, _ = EvidenceManager.detect_format(test_db, raw_dd_evidence.id)
    first_id = storage_first.id

    storage_second, _ = EvidenceManager.detect_format(test_db, raw_dd_evidence.id)

    assert storage_second.id == first_id
    rows = test_db.query(Storage).filter(Storage.evidence_id == raw_dd_evidence.id).all()
    assert len(rows) == 1


def test_detect_format_missing_evidence_raises(test_db):
    with pytest.raises(ValueError, match="not found"):
        EvidenceManager.detect_format(test_db, 99999)


def test_detect_format_never_writes_to_source(test_db, raw_dd_evidence: Evidence):
    source_path = Path(raw_dd_evidence.source_path)
    before = source_path.read_bytes()

    EvidenceManager.detect_format(test_db, raw_dd_evidence.id)

    assert source_path.read_bytes() == before
