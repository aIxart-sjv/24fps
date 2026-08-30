"""
MD5 hash computation.

Master Specification Section 3: MD5 is calculated because NTRO explicitly
requires it. It must not be described as a modern secure hash — SHA-256
remains the primary integrity hash.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 65536


def md5_file(path: Path) -> str:
    """Compute the MD5 hex digest of a file using streamed reads.

    Args:
        path: Path to the file to hash.

    Returns:
        Lowercase hex-encoded MD5 digest.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be read.
    """
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()
