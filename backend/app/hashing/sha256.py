"""
SHA-256 hash computation.
Master Specification Section 3 (Evidence Hashing), Section 38 (Integrity Engine).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 65536


def sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file using streamed reads.

    Args:
        path: Path to the file to hash.

    Returns:
        Lowercase hex-encoded SHA-256 digest.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be read.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute the SHA-256 hex digest of an in-memory byte string.

    The in-memory counterpart to `sha256_file` -- added in Phase 16 (the
    hash-linked audit chain hashes canonical JSON bytes, not a file) so
    every SHA-256 computation in the codebase funnels through this one
    module rather than a second call to `hashlib.sha256` elsewhere.

    Args:
        data: The bytes to hash.

    Returns:
        Lowercase hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(data).hexdigest()
