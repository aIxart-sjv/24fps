"""Tests for Phase 4A evidence-source path safety."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.evidence_manager import EvidenceManager
from app.models import Case, CaseStatus
from app.schemas.evidence import EvidenceCreateRequest
from app.utils.paths import resolve_evidence_source_path


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
    """Create a case that can own registered evidence."""
    case = Case(case_id="PATH-001", name="Path Safety", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()
    return case


def test_register_evidence_accepts_and_preserves_source(
    test_db, registered_case: Case, evidence_root: Path
):
    """A root-contained source is stored canonically without being changed."""
    source = evidence_root / "images" / "source.dd"
    source.parent.mkdir()
    source.write_bytes(b"preserved source evidence")
    before = source.stat()

    evidence = EvidenceManager.register_evidence(
        test_db,
        registered_case.id,
        EvidenceCreateRequest(
            evidence_id="PATH-E001",
            source_type="forensic_image",
            source_path="images/source.dd",
        ),
    )

    after = source.stat()
    assert evidence.source_path == str(source.resolve())
    assert source.read_bytes() == b"preserved source evidence"
    assert stat.S_IMODE(after.st_mode) == stat.S_IMODE(before.st_mode)
    assert after.st_mtime_ns == before.st_mtime_ns


def test_register_evidence_rejects_path_traversal(
    test_db, registered_case: Case, evidence_root: Path, tmp_path: Path
):
    """Traversal is rejected even when the target exists outside the root."""
    outside_source = tmp_path / "outside.dd"
    outside_source.write_bytes(b"outside root")

    with pytest.raises(ValueError, match="path traversal"):
        EvidenceManager.register_evidence(
            test_db,
            registered_case.id,
            EvidenceCreateRequest(
                evidence_id="PATH-E002",
                source_type="forensic_image",
                source_path="../outside.dd",
            ),
        )


def test_register_evidence_rejects_outside_root_path(
    test_db, registered_case: Case, evidence_root: Path, tmp_path: Path
):
    """Absolute sources outside the configured root are rejected."""
    outside_source = tmp_path / "outside.dd"
    outside_source.write_bytes(b"outside root")

    with pytest.raises(ValueError, match="inside EVIDENCE_ROOT"):
        EvidenceManager.register_evidence(
            test_db,
            registered_case.id,
            EvidenceCreateRequest(
                evidence_id="PATH-E003",
                source_type="forensic_image",
                source_path=str(outside_source),
            ),
        )


@pytest.mark.parametrize("source_path", ["", "   ", "missing.dd"])
def test_resolve_evidence_source_path_rejects_invalid_input(evidence_root: Path, source_path: str):
    """Empty and nonexistent source paths are invalid."""
    with pytest.raises(ValueError):
        resolve_evidence_source_path(source_path, evidence_root)


def test_register_evidence_api_rejects_unsafe_source_path(
    test_client, test_db, evidence_root: Path
):
    """The existing registration endpoint returns a client error for unsafe paths."""
    case = Case(case_id="PATH-API-001", name="Path Safety API", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    response = test_client.post(
        f"/api/v1/cases/{case.id}/evidence",
        json={
            "evidence_id": "PATH-E004",
            "source_type": "forensic_image",
            "source_path": "../outside.dd",
        },
    )

    assert response.status_code == 400
    assert "path traversal" in response.json()["detail"]
