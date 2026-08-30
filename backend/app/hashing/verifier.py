"""
Hash comparison utilities.
Master Specification Section 38 (Integrity Engine): compare_hashes, verify_hash.
"""

from __future__ import annotations

from pathlib import Path

from app.hashing.md5 import md5_file
from app.hashing.sha256 import sha256_file

_ALGORITHM_FUNCTIONS = {
    "sha256": sha256_file,
    "md5": md5_file,
}


def compare_hashes(a: str, b: str) -> bool:
    """Compare two hex digests case-insensitively.

    Args:
        a: First hex digest.
        b: Second hex digest.

    Returns:
        True if the digests represent the same value.
    """
    return a.strip().lower() == b.strip().lower()


def verify_hash(path: Path, expected: str, algorithm: str) -> bool:
    """Recompute a file's hash and compare it against an expected value.

    Args:
        path: Path to the file to verify.
        expected: The expected hex digest.
        algorithm: One of "sha256" or "md5".

    Returns:
        True if the recomputed hash matches the expected value.

    Raises:
        ValueError: If the algorithm is not supported.
        FileNotFoundError: If the file does not exist.
    """
    hash_function = _ALGORITHM_FUNCTIONS.get(algorithm)
    if hash_function is None:
        raise ValueError(f"Unsupported hash algorithm: {algorithm!r}")
    return compare_hashes(hash_function(path), expected)
