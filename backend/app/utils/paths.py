"""Safe filesystem path handling for preserved evidence and derived artifacts."""

from __future__ import annotations

from pathlib import Path


def resolve_evidence_source_path(source_path: str, evidence_root: Path) -> Path:
    """Resolve an existing evidence source strictly inside ``evidence_root``.

    Relative paths are interpreted from the configured evidence root.  The
    function only inspects filesystem metadata; it never writes to, moves, or
    changes permissions on the source evidence.

    Args:
        source_path: Absolute or evidence-root-relative source path.
        evidence_root: Configured root for preserved source evidence.

    Returns:
        The canonical absolute source path.

    Raises:
        ValueError: If the path is empty, contains traversal, does not exist,
            is outside the configured root, or is not a regular file/directory.
    """
    if not isinstance(source_path, str) or not source_path.strip():
        raise ValueError("Evidence source_path must be a non-empty path")
    if "\x00" in source_path:
        raise ValueError("Evidence source_path contains an invalid null byte")

    supplied_path = Path(source_path).expanduser()
    if ".." in supplied_path.parts:
        raise ValueError("Evidence source_path must not contain path traversal")

    try:
        resolved_root = evidence_root.expanduser().resolve(strict=True)
        candidate = supplied_path if supplied_path.is_absolute() else resolved_root / supplied_path
        resolved_source = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Evidence source_path does not exist or cannot be resolved") from exc

    if resolved_source == resolved_root:
        raise ValueError("Evidence source_path must identify an item inside EVIDENCE_ROOT")
    try:
        resolved_source.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Evidence source_path must resolve inside EVIDENCE_ROOT") from exc

    if not resolved_source.is_file() and not resolved_source.is_dir():
        raise ValueError("Evidence source_path must be an existing regular file or directory")

    return resolved_source


def resolve_path_within_root(relative_path: str, root: Path) -> Path:
    """Resolve ``relative_path`` strictly inside ``root``, without requiring it to exist.

    Unlike `resolve_evidence_source_path`, the target itself is allowed to be
    new (derived output that is about to be created), so this cannot resolve
    the full candidate with ``strict=True``. Instead every *existing*
    intermediate component is resolved first (following any symlinks), and
    only the non-existent tail is appended, which is what stops a symlink
    planted inside ``root`` from redirecting the write outside of it.

    Args:
        relative_path: A root-relative path. Must not be absolute and must
            not contain ``..`` traversal segments.
        root: The configured filesystem root the path must resolve inside
            of (e.g. ARTIFACT_ROOT).

    Returns:
        The canonical absolute path, guaranteed to be inside ``root``.

    Raises:
        ValueError: If the path is empty, absolute, contains traversal or a
            null byte, the root cannot be resolved, the resolved path
            escapes the root (including via a symlink), or the resolved
            path identifies the root itself rather than an item inside it.
    """
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("path must be a non-empty relative path")
    if "\x00" in relative_path:
        raise ValueError("path contains an invalid null byte")

    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError("path must be relative, not absolute")
    if ".." in candidate.parts:
        raise ValueError("path must not contain path traversal")

    try:
        resolved_root = root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("configured root does not exist or cannot be resolved") from exc

    resolved_candidate = (resolved_root / candidate).resolve(strict=False)

    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("path escapes the configured root") from exc

    if resolved_candidate == resolved_root:
        raise ValueError("path must identify an item inside the configured root")

    return resolved_candidate
