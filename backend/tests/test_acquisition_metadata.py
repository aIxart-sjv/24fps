"""Tests for EvidenceManager.record_acquisition_metadata (Phase 5 acquisition glue)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.acquisition import open_reader
from app.acquisition.e01_handler import E01UnavailableError
from app.config import get_settings
from app.core.evidence_manager import EvidenceManager
from app.models import Artifact, Case, CaseStatus, Evidence


@pytest.fixture
def artifact_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setenv("ARTIFACT_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.fixture
def evidence_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.fixture
def raw_dd_evidence(test_db, artifact_root: Path, evidence_root: Path) -> Evidence:
    """A Case + Evidence registered against a real RAW/DD image file."""
    case = Case(case_id="ACQ-CASE-001", name="Acquisition Metadata Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    image_path = evidence_root / "image.dd"
    image_path.write_bytes(b"\xaa\xbb\xcc\xdd" * 256)

    evidence = Evidence(
        evidence_id="ACQ-E001",
        case_id=case.id,
        source_type="raw_dd",
        source_path=str(image_path.resolve()),
    )
    test_db.add(evidence)
    test_db.commit()
    return evidence


def test_record_acquisition_metadata_creates_manifest_artifact(test_db, raw_dd_evidence: Evidence):
    artifact = EvidenceManager.record_acquisition_metadata(
        test_db, raw_dd_evidence.id, tool_version="24fps-test"
    )

    assert isinstance(artifact, Artifact)
    assert artifact.evidence_id == raw_dd_evidence.id
    assert artifact.artifact_type == "acquisition_manifest"
    assert artifact.tool_version == "24fps-test"
    assert artifact.path.endswith("manifest.json")
    assert artifact.size_bytes is not None and artifact.size_bytes > 0
    assert artifact.sha256 is not None
    assert artifact.md5 is not None


def test_record_acquisition_metadata_manifest_content_matches_reader(
    test_db, raw_dd_evidence: Evidence
):
    artifact = EvidenceManager.record_acquisition_metadata(test_db, raw_dd_evidence.id)

    manifest = json.loads(Path(artifact.path).read_text(encoding="utf-8"))
    assert manifest["evidence_id"] == "ACQ-E001"
    assert manifest["source_type"] == "raw_dd"
    assert manifest["reader_metadata"]["format"] == "raw_dd"

    reader = open_reader("raw_dd", Path(raw_dd_evidence.source_path))
    try:
        assert manifest["reader_metadata"]["size_bytes"] == reader.size()
    finally:
        reader.close()


def test_record_acquisition_metadata_never_writes_to_source(test_db, raw_dd_evidence: Evidence):
    source_path = Path(raw_dd_evidence.source_path)
    before = source_path.read_bytes()

    EvidenceManager.record_acquisition_metadata(test_db, raw_dd_evidence.id)

    assert source_path.read_bytes() == before


def test_record_acquisition_metadata_missing_evidence_raises(
    test_db, artifact_root: Path, evidence_root: Path
):
    with pytest.raises(ValueError, match="not found"):
        EvidenceManager.record_acquisition_metadata(test_db, 99999)


def test_record_acquisition_metadata_e01_without_libewf_raises_clearly(
    test_db, artifact_root: Path, evidence_root: Path, monkeypatch: pytest.MonkeyPatch
):
    """An E01 evidence item must fail clearly, not silently, when libewf is unavailable."""
    from app.acquisition import e01_handler

    monkeypatch.setattr(e01_handler, "pyewf", None)

    case = Case(case_id="ACQ-CASE-002", name="E01 Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()
    fake_e01 = evidence_root / "image.E01"
    fake_e01.write_bytes(b"placeholder")
    evidence = Evidence(
        evidence_id="ACQ-E002",
        case_id=case.id,
        source_type="e01",
        source_path=str(fake_e01.resolve()),
    )
    test_db.add(evidence)
    test_db.commit()

    with pytest.raises(E01UnavailableError):
        EvidenceManager.record_acquisition_metadata(test_db, evidence.id)


def test_record_acquisition_metadata_rejects_directory_export(
    test_db, artifact_root: Path, evidence_root: Path
):
    case = Case(case_id="ACQ-CASE-003", name="Directory Export Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()
    export_dir = evidence_root / "export"
    export_dir.mkdir()
    (export_dir / "file.mp4").write_bytes(b"data")
    evidence = Evidence(
        evidence_id="ACQ-E003",
        case_id=case.id,
        source_type="native_export",
        source_path=str(export_dir.resolve()),
    )
    test_db.add(evidence)
    test_db.commit()

    with pytest.raises(ValueError, match="directory"):
        EvidenceManager.record_acquisition_metadata(test_db, evidence.id)
