"""
Tests for pure hashing primitives and fingerprint/manifest utilities.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from app.hashing.md5 import md5_file
from app.hashing.sha256 import sha256_file
from app.hashing.verifier import compare_hashes, verify_hash
from app.integrity.evidence_fingerprint import compute_evidence_fingerprint
from app.integrity.manifest import generate_manifest, verify_manifest
from app.models.hash import EvidenceHash, HashAlgorithm, VerificationStatus


@pytest.fixture
def sample_file(tmp_path):
    """Create a small file with known content and known digests."""
    content = b"24FPS forensic evidence sample content"
    path = tmp_path / "sample.bin"
    path.write_bytes(content)
    return path, content


def test_sha256_file(sample_file):
    path, content = sample_file
    expected = hashlib.sha256(content).hexdigest()
    assert sha256_file(path) == expected


def test_md5_file(sample_file):
    path, content = sample_file
    expected = hashlib.md5(content).hexdigest()
    assert md5_file(path) == expected


def test_sha256_file_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        sha256_file(tmp_path / "does_not_exist.bin")


def test_compare_hashes_case_insensitive():
    assert compare_hashes("ABC123", "abc123") is True
    assert compare_hashes("abc123", "def456") is False


def test_verify_hash_matches(sample_file):
    path, content = sample_file
    expected = hashlib.sha256(content).hexdigest()
    assert verify_hash(path, expected, "sha256") is True


def test_verify_hash_mismatch(sample_file):
    path, _ = sample_file
    assert verify_hash(path, "0" * 64, "sha256") is False


def test_verify_hash_unsupported_algorithm(sample_file):
    path, _ = sample_file
    with pytest.raises(ValueError):
        verify_hash(path, "abc", "sha1")


def test_compute_evidence_fingerprint(sample_file):
    path, content = sample_file
    fingerprint = compute_evidence_fingerprint(path)
    assert fingerprint.sha256 == hashlib.sha256(content).hexdigest()
    assert fingerprint.md5 == hashlib.md5(content).hexdigest()


def test_generate_and_verify_manifest():
    hash_row = EvidenceHash(
        id=1,
        evidence_id=42,
        algorithm=HashAlgorithm.SHA256,
        hash_value="a" * 64,
        software_version="0.1.0",
        source_reference="/evidence/E001/image.dd",
        verification_status=VerificationStatus.NOT_VERIFIED,
    )
    hash_row.calculated_at = datetime.now(UTC)

    manifest = generate_manifest(42, [hash_row])
    assert manifest["evidence_id"] == 42
    assert manifest["hashes"][0]["algorithm"] == "sha256"
    assert manifest["hashes"][0]["hash"] == "a" * 64

    assert verify_manifest(manifest, [hash_row]) is True

    hash_row.hash_value = "b" * 64
    assert verify_manifest(manifest, [hash_row]) is False


def test_verify_manifest_rejects_missing_or_extra_hashes():
    sha256_row = EvidenceHash(
        id=1,
        evidence_id=42,
        algorithm=HashAlgorithm.SHA256,
        hash_value="a" * 64,
        verification_status=VerificationStatus.NOT_VERIFIED,
    )
    md5_row = EvidenceHash(
        id=2,
        evidence_id=42,
        algorithm=HashAlgorithm.MD5,
        hash_value="b" * 32,
        verification_status=VerificationStatus.NOT_VERIFIED,
    )
    calculated_at = datetime.now(UTC)
    sha256_row.calculated_at = calculated_at
    md5_row.calculated_at = calculated_at

    manifest = generate_manifest(42, [sha256_row, md5_row])

    manifest["hashes"].pop()
    assert verify_manifest(manifest, [sha256_row, md5_row]) is False

    assert verify_manifest(generate_manifest(42, [sha256_row, md5_row]), [sha256_row]) is False
