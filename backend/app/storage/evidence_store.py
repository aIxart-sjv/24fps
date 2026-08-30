"""
Evidence storage abstraction — preserved-evidence root layout.
Master Specification Section 52 (Storage Layout), Section 53
("Temporary vs Preserved Data").

This module resolves *where* preserved companion data for a registered
evidence item lives (e.g. acquisition manifests written once, at
acquisition time). It never writes derived output — that belongs under
ARTIFACT_ROOT via `app.storage.artifact_store` — and it never mutates an
already-registered evidence source, which is guarded separately by
`app.utils.paths.resolve_evidence_source_path`.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.utils.paths import resolve_path_within_root


def _validate_identifier(value: str, label: str) -> str:
    """Reject an identifier that could smuggle extra path components.

    Args:
        value: A case_id or evidence_id string supplied by a caller.
        label: Human-readable name of the field, for error messages.

    Returns:
        The validated identifier, unchanged.

    Raises:
        ValueError: If the identifier is empty or contains characters that
            would change the shape of the resolved directory path.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    if "/" in value or "\\" in value or "\x00" in value:
        raise ValueError(f"{label} must not contain path separators")
    if value in (".", ".."):
        raise ValueError(f"{label} must not be '.' or '..'")
    return value


def resolve_preserved_evidence_directory(case_id: str, evidence_id: str) -> Path:
    """Resolve the preserved-evidence directory for one evidence item.

    The directory is resolved strictly inside the configured EVIDENCE_ROOT
    at ``EVIDENCE_ROOT/<case_id>/<evidence_id>``. It is not created here;
    callers that need it to exist (e.g. before writing a preserved
    acquisition manifest) must create it explicitly.

    Args:
        case_id: The owning case's public case_id identifier.
        evidence_id: The evidence item's public evidence_id identifier.

    Returns:
        The canonical absolute preserved-evidence directory path.

    Raises:
        ValueError: If either identifier is unsafe, or the resolved path
            would escape EVIDENCE_ROOT.
    """
    case_id = _validate_identifier(case_id, "case_id")
    evidence_id = _validate_identifier(evidence_id, "evidence_id")

    settings = get_settings()
    relative = f"{case_id}/{evidence_id}"
    return resolve_path_within_root(relative, settings.evidence_root)
