"""
Combined SHA-256 + MD5 fingerprint computation for evidence files.

Reads the source file once and updates both digests incrementally,
rather than reading it twice via separate sha256_file/md5_file calls.
Per Master Specification Section 60, large evidence files must not be
hashed via multiple full-file passes when one streamed pass suffices.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

_CHUNK_SIZE = 65536


@dataclass(frozen=True)
class EvidenceFingerprint:
    """SHA-256 and MD5 digests computed from a single read of a file."""

    sha256: str
    md5: str


def compute_evidence_fingerprint(path: Path) -> EvidenceFingerprint:
    """Compute SHA-256 and MD5 digests of a file in a single streamed pass.

    Args:
        path: Path to the evidence file to fingerprint.

    Returns:
        An `EvidenceFingerprint` with both digests.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be read.
    """
    sha256_digest = hashlib.sha256()
    md5_digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            sha256_digest.update(chunk)
            md5_digest.update(chunk)
    return EvidenceFingerprint(sha256=sha256_digest.hexdigest(), md5=md5_digest.hexdigest())
