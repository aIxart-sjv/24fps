"""
Artifact storage abstraction — root-bound path handling for derived output.
Master Specification Section 20 (Media Artifact Model), Section 53
("Temporary vs Preserved Data": DERIVED output lives apart from PRESERVED
source evidence).

Section 53 draws REPORT (JSON/PDF/HTML/CSV) as its own category, distinct
from DERIVED (recovered recordings, AI results, ...) -- both configured
separately (`ARTIFACT_ROOT` vs `REPORT_ROOT`, Section 67). Phase 18
(`app.core.report_manager.ReportManager`) reuses the same root-bound path
safety mechanism as artifacts (`resolve_path_within_root`, the
evidence-root-overlap guard) rather than building a second file-storage
system, just bound to `REPORT_ROOT` instead of `ARTIFACT_ROOT`.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.utils.paths import resolve_path_within_root


def resolve_artifact_path(relative_path: str) -> Path:
    """Resolve a derived-artifact path strictly inside the configured ARTIFACT_ROOT.

    Rejects traversal and symlink escape (via `resolve_path_within_root`),
    then additionally rejects any resolved path that also falls inside the
    configured EVIDENCE_ROOT. The second check exists so that a misconfigured
    deployment (ARTIFACT_ROOT pointed at or nested inside EVIDENCE_ROOT)
    cannot silently let derived output land inside preserved source evidence.

    Args:
        relative_path: A root-relative path supplied by the caller
            (never treated as an absolute/arbitrary filesystem path).

    Returns:
        The canonical absolute path, guaranteed to be inside ARTIFACT_ROOT
        and outside EVIDENCE_ROOT.

    Raises:
        ValueError: If the path is invalid, escapes ARTIFACT_ROOT, or
            overlaps EVIDENCE_ROOT.
    """
    settings = get_settings()
    resolved = resolve_path_within_root(relative_path, settings.artifact_root)

    evidence_root = settings.evidence_root.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(evidence_root)
    except ValueError:
        pass
    else:
        raise ValueError("artifact path must not overlap the preserved evidence root")

    return resolved


def prepare_artifact_directory(relative_path: str) -> Path:
    """Resolve an artifact path inside ARTIFACT_ROOT and create its parent directory.

    This only prepares the destination directory; it never creates or
    writes the artifact file itself — that remains the responsibility of
    the later-phase component (acquisition, recovery, AI, reporting) that
    actually produces the artifact's bytes.

    Args:
        relative_path: A root-relative path, as accepted by `resolve_artifact_path`.

    Returns:
        The canonical absolute artifact path with its parent directory
        guaranteed to exist.

    Raises:
        ValueError: If the path is invalid, escapes ARTIFACT_ROOT, or
            overlaps EVIDENCE_ROOT.
    """
    resolved = resolve_artifact_path(relative_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def resolve_report_path(relative_path: str) -> Path:
    """Resolve a generated-report path strictly inside the configured
    REPORT_ROOT (never inside ARTIFACT_ROOT or EVIDENCE_ROOT).

    Mirrors `resolve_artifact_path` exactly, bound to a different root --
    Section 53 treats REPORT output (JSON/PDF/HTML/CSV) as its own
    category, separate from DERIVED artifacts.

    Args:
        relative_path: A root-relative path supplied by the caller
            (never treated as an absolute/arbitrary filesystem path).

    Returns:
        The canonical absolute path, guaranteed to be inside REPORT_ROOT
        and outside EVIDENCE_ROOT.

    Raises:
        ValueError: If the path is invalid, escapes REPORT_ROOT, or
            overlaps EVIDENCE_ROOT.
    """
    settings = get_settings()
    resolved = resolve_path_within_root(relative_path, settings.report_root)

    evidence_root = settings.evidence_root.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(evidence_root)
    except ValueError:
        pass
    else:
        raise ValueError("report path must not overlap the preserved evidence root")

    return resolved


def prepare_report_directory(relative_path: str) -> Path:
    """Resolve a report path inside REPORT_ROOT and create its parent directory.

    This only prepares the destination directory; it never writes the
    report file itself -- that remains `app.core.report_manager.
    ReportManager`'s responsibility.

    Args:
        relative_path: A root-relative path, as accepted by `resolve_report_path`.

    Returns:
        The canonical absolute report path with its parent directory
        guaranteed to exist.

    Raises:
        ValueError: If the path is invalid, escapes REPORT_ROOT, or
            overlaps EVIDENCE_ROOT.
    """
    resolved = resolve_report_path(relative_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved
