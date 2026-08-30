"""Tests for Phase 4 root-bound path handling (evidence_store, artifact_store)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings
from app.storage.artifact_store import prepare_artifact_directory, resolve_artifact_path
from app.storage.evidence_store import resolve_preserved_evidence_directory
from app.utils.paths import resolve_path_within_root


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
    """Configure an isolated EVIDENCE_ROOT for a test."""
    root = tmp_path / "evidence"
    root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


# --- resolve_path_within_root (generic root-bound resolver) ---


def test_resolve_path_within_root_accepts_relative_path(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()

    resolved = resolve_path_within_root("sub/dir/file.bin", root)

    assert resolved == (root.resolve() / "sub" / "dir" / "file.bin")


@pytest.mark.parametrize("bad_path", ["", "   ", "/etc/passwd", "../escape.bin", "a/../../escape"])
def test_resolve_path_within_root_rejects_unsafe_input(tmp_path: Path, bad_path: str):
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(ValueError):
        resolve_path_within_root(bad_path, root)


def test_resolve_path_within_root_rejects_symlink_escape(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    (root / "escape_link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes the configured root"):
        resolve_path_within_root("escape_link/payload.bin", root)


@pytest.mark.parametrize("root_identifying_path", [".", "./"])
def test_resolve_path_within_root_rejects_the_root_itself(
    tmp_path: Path, root_identifying_path: str
):
    """A candidate resolving to the root itself is not a valid item inside it."""
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(ValueError, match="must identify an item inside the configured root"):
        resolve_path_within_root(root_identifying_path, root)


def test_resolve_path_within_root_missing_root_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        resolve_path_within_root("file.bin", tmp_path / "does_not_exist")


# --- artifact_store.resolve_artifact_path ---


def test_resolve_artifact_path_stays_inside_artifact_root(artifact_root: Path, evidence_root: Path):
    resolved = resolve_artifact_path("CASE-1/E001/recovered.mp4")

    assert resolved == (artifact_root.resolve() / "CASE-1" / "E001" / "recovered.mp4")
    resolved.relative_to(artifact_root.resolve())


def test_resolve_artifact_path_rejects_traversal(artifact_root: Path, evidence_root: Path):
    with pytest.raises(ValueError):
        resolve_artifact_path("../outside.mp4")


def test_resolve_artifact_path_rejects_symlink_escape(artifact_root: Path, evidence_root: Path):
    outside = artifact_root.parent / "outside_target"
    outside.mkdir()
    (artifact_root / "sneaky").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes the configured root"):
        resolve_artifact_path("sneaky/payload.mp4")


def test_resolve_artifact_path_rejects_overlap_with_evidence_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A misconfigured deployment must not let derived output land in preserved evidence."""
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    nested_evidence_root = artifact_root / "evidence_overlap"
    nested_evidence_root.mkdir()

    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("EVIDENCE_ROOT", str(nested_evidence_root))
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="preserved evidence root"):
            resolve_artifact_path("evidence_overlap/derived.mp4")
    finally:
        get_settings.cache_clear()


def test_prepare_artifact_directory_creates_parent_only(artifact_root: Path, evidence_root: Path):
    resolved = prepare_artifact_directory("CASE-1/E001/recovered.mp4")

    assert resolved.parent.is_dir()
    assert not resolved.exists()


# --- evidence_store.resolve_preserved_evidence_directory ---


def test_resolve_preserved_evidence_directory_stays_inside_evidence_root(evidence_root: Path):
    resolved = resolve_preserved_evidence_directory("CASE-1", "E001")

    assert resolved == (evidence_root.resolve() / "CASE-1" / "E001")


@pytest.mark.parametrize("bad_id", ["", "  ", "../escape", "a/b", "a\\b", "."])
def test_resolve_preserved_evidence_directory_rejects_unsafe_identifiers(
    evidence_root: Path, bad_id: str
):
    with pytest.raises(ValueError):
        resolve_preserved_evidence_directory(bad_id, "E001")
    with pytest.raises(ValueError):
        resolve_preserved_evidence_directory("CASE-1", bad_id)
