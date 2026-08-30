"""Tests for the Artifact model and EvidenceManager artifact registration."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings
from app.core.evidence_manager import EvidenceManager
from app.models import Artifact, Case, CaseStatus, Evidence
from app.schemas.artifact import ArtifactCreateRequest


@pytest.fixture
def artifact_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Configure an isolated ARTIFACT_ROOT for a test."""
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setenv("ARTIFACT_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.fixture
def evidence_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Configure an isolated EVIDENCE_ROOT for a test, distinct from artifact_root."""
    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


@pytest.fixture
def registered_evidence(test_db, artifact_root: Path, evidence_root: Path) -> Evidence:
    """Create a case and evidence item that can own registered artifacts."""
    case = Case(case_id="ART-CASE-001", name="Artifact Test Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(evidence_id="ART-E001", case_id=case.id, source_type="forensic_image")
    test_db.add(evidence)
    test_db.commit()
    return evidence


def test_register_artifact_creates_row_with_expected_fields(test_db, registered_evidence: Evidence):
    artifact = EvidenceManager.register_artifact(
        test_db,
        registered_evidence.id,
        ArtifactCreateRequest(
            relative_path="ART-CASE-001/ART-E001/image.dd",
            artifact_type="forensic_image",
            size_bytes=1024,
            sha256="a" * 64,
            md5="b" * 32,
            created_by="examiner-1",
            tool_version="24fps-0.1.0",
        ),
    )

    assert artifact.id is not None
    assert artifact.evidence_id == registered_evidence.id
    assert artifact.parent_artifact_id is None
    assert artifact.artifact_type == "forensic_image"
    assert artifact.status == "registered"
    assert artifact.path.endswith("ART-CASE-001/ART-E001/image.dd")
    assert Path(artifact.path).parent.is_dir()
    assert not Path(artifact.path).exists()


def test_register_artifact_missing_evidence_raises(
    test_db, artifact_root: Path, evidence_root: Path
):
    with pytest.raises(ValueError, match="not found"):
        EvidenceManager.register_artifact(
            test_db,
            99999,
            ArtifactCreateRequest(relative_path="x/y.mp4", artifact_type="recovered_recording"),
        )


def test_register_artifact_rejects_traversal(test_db, registered_evidence: Evidence):
    with pytest.raises(ValueError):
        EvidenceManager.register_artifact(
            test_db,
            registered_evidence.id,
            ArtifactCreateRequest(relative_path="../escape.dd", artifact_type="forensic_image"),
        )


def test_register_artifact_duplicate_path_raises(test_db, registered_evidence: Evidence):
    request = ArtifactCreateRequest(
        relative_path="ART-CASE-001/ART-E001/dup.dd", artifact_type="forensic_image"
    )
    EvidenceManager.register_artifact(test_db, registered_evidence.id, request)

    with pytest.raises(ValueError, match="already registered"):
        EvidenceManager.register_artifact(test_db, registered_evidence.id, request)


def test_register_artifact_parent_lineage(test_db, registered_evidence: Evidence):
    parent = EvidenceManager.register_artifact(
        test_db,
        registered_evidence.id,
        ArtifactCreateRequest(
            relative_path="ART-CASE-001/ART-E001/image.dd", artifact_type="forensic_image"
        ),
    )
    child = EvidenceManager.register_artifact(
        test_db,
        registered_evidence.id,
        ArtifactCreateRequest(
            relative_path="ART-CASE-001/ART-E001/recovered/rec001.mp4",
            artifact_type="recovered_recording",
            parent_artifact_id=parent.id,
        ),
    )

    assert child.parent_artifact_id == parent.id
    test_db.refresh(parent)
    assert child in parent.child_artifacts
    assert child.parent_artifact is not None
    assert child.parent_artifact.id == parent.id


def test_register_artifact_rejects_parent_from_different_evidence(
    test_db, registered_evidence: Evidence, artifact_root: Path, evidence_root: Path
):
    other_case = Case(case_id="ART-CASE-002", name="Other Case", status=CaseStatus.DRAFT)
    test_db.add(other_case)
    test_db.commit()
    other_evidence = Evidence(
        evidence_id="ART-E002", case_id=other_case.id, source_type="forensic_image"
    )
    test_db.add(other_evidence)
    test_db.commit()

    unrelated_parent = EvidenceManager.register_artifact(
        test_db,
        other_evidence.id,
        ArtifactCreateRequest(
            relative_path="ART-CASE-002/ART-E002/image.dd", artifact_type="forensic_image"
        ),
    )

    with pytest.raises(ValueError, match="does not reference an artifact belonging to evidence"):
        EvidenceManager.register_artifact(
            test_db,
            registered_evidence.id,
            ArtifactCreateRequest(
                relative_path="ART-CASE-001/ART-E001/rec.mp4",
                artifact_type="recovered_recording",
                parent_artifact_id=unrelated_parent.id,
            ),
        )


def test_register_artifact_missing_parent_raises(test_db, registered_evidence: Evidence):
    with pytest.raises(ValueError, match="does not reference an artifact"):
        EvidenceManager.register_artifact(
            test_db,
            registered_evidence.id,
            ArtifactCreateRequest(
                relative_path="ART-CASE-001/ART-E001/rec.mp4",
                artifact_type="recovered_recording",
                parent_artifact_id=99999,
            ),
        )


def test_register_artifact_never_writes_into_evidence_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, test_db
):
    """A misconfigured overlap between roots must still be rejected during registration."""
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    nested_evidence_root = artifact_root / "evidence_overlap"
    nested_evidence_root.mkdir()
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("EVIDENCE_ROOT", str(nested_evidence_root))
    get_settings.cache_clear()

    try:
        case = Case(case_id="ART-CASE-003", name="Overlap Case", status=CaseStatus.DRAFT)
        test_db.add(case)
        test_db.commit()
        evidence = Evidence(evidence_id="ART-E003", case_id=case.id, source_type="forensic_image")
        test_db.add(evidence)
        test_db.commit()

        with pytest.raises(ValueError, match="preserved evidence root"):
            EvidenceManager.register_artifact(
                test_db,
                evidence.id,
                ArtifactCreateRequest(
                    relative_path="evidence_overlap/derived.mp4", artifact_type="forensic_image"
                ),
            )
    finally:
        get_settings.cache_clear()


def test_list_evidence_artifacts(test_db, registered_evidence: Evidence):
    EvidenceManager.register_artifact(
        test_db,
        registered_evidence.id,
        ArtifactCreateRequest(
            relative_path="ART-CASE-001/ART-E001/a.dd", artifact_type="forensic_image"
        ),
    )
    EvidenceManager.register_artifact(
        test_db,
        registered_evidence.id,
        ArtifactCreateRequest(
            relative_path="ART-CASE-001/ART-E001/b.dd", artifact_type="forensic_image"
        ),
    )

    artifacts = EvidenceManager.list_evidence_artifacts(test_db, registered_evidence.id)

    assert len(artifacts) == 2
    assert all(isinstance(a, Artifact) for a in artifacts)


def test_list_evidence_artifacts_missing_evidence_raises(test_db):
    with pytest.raises(ValueError, match="not found"):
        EvidenceManager.list_evidence_artifacts(test_db, 99999)


def test_evidence_artifact_relationship(test_db, registered_evidence: Evidence):
    EvidenceManager.register_artifact(
        test_db,
        registered_evidence.id,
        ArtifactCreateRequest(
            relative_path="ART-CASE-001/ART-E001/a.dd", artifact_type="forensic_image"
        ),
    )

    test_db.refresh(registered_evidence)
    assert len(registered_evidence.artifacts) == 1
    assert registered_evidence.artifacts[0].evidence_id == registered_evidence.id
