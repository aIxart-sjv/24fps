"""Tests for native-export registration (Master Spec Section 9, Path 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.acquisition.native_export import NATIVE_EXPORT_SOURCE_TYPE
from app.config import get_settings
from app.core.evidence_manager import EvidenceManager
from app.models import Case, CaseStatus
from app.schemas.acquisition import NativeExportRegisterRequest


@pytest.fixture
def evidence_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Configure an isolated preserved-evidence root for a test."""
    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.fixture
def registered_case(test_db) -> Case:
    case = Case(case_id="NX-CASE-001", name="Native Export Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()
    return case


def test_register_native_export_pins_source_type(
    test_db, registered_case: Case, evidence_root: Path
):
    export_dir = evidence_root / "export"
    export_dir.mkdir()
    (export_dir / "channel1.mp4").write_bytes(b"exported recording bytes")
    (export_dir / "player.exe").write_bytes(b"vendor player stub")

    evidence = EvidenceManager.register_native_export(
        test_db,
        registered_case.id,
        NativeExportRegisterRequest(
            evidence_id="NX-E001",
            source_path="export",
            source_description="Includes vendor player and export log",
        ),
    )

    assert evidence.source_type == NATIVE_EXPORT_SOURCE_TYPE
    assert evidence.source_type == "native_export"
    assert evidence.source_path == str(export_dir.resolve())
    assert evidence.source_description == "Includes vendor player and export log"


def test_register_native_export_reuses_path_safety_validation(
    test_db, registered_case: Case, evidence_root: Path
):
    """Traversal outside EVIDENCE_ROOT must be rejected exactly as for any other evidence."""
    with pytest.raises(ValueError, match="path traversal"):
        EvidenceManager.register_native_export(
            test_db,
            registered_case.id,
            NativeExportRegisterRequest(evidence_id="NX-E002", source_path="../outside"),
        )


def test_register_native_export_rejects_duplicate_evidence_id(
    test_db, registered_case: Case, evidence_root: Path
):
    export_dir = evidence_root / "export"
    export_dir.mkdir()
    (export_dir / "file.mp4").write_bytes(b"data")

    request = NativeExportRegisterRequest(evidence_id="NX-E003", source_path="export")
    EvidenceManager.register_native_export(test_db, registered_case.id, request)

    with pytest.raises(ValueError, match="already exists"):
        EvidenceManager.register_native_export(test_db, registered_case.id, request)


def test_register_native_export_missing_case_raises(test_db, evidence_root: Path):
    with pytest.raises(ValueError, match="not found"):
        EvidenceManager.register_native_export(
            test_db,
            99999,
            NativeExportRegisterRequest(evidence_id="NX-E004", source_path="export"),
        )
