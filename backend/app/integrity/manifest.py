"""
Hash manifest construction and verification.
Master Specification Section 38 (Integrity Engine): generate_manifest, verify_manifest.

A manifest is a structured, machine-readable snapshot of an evidence
item's recorded hashes (Section 20: "Structured JSON = machine-readable
evidence representation"). It is a report of stored state, not a
re-hash of the source file — use IntegrityManager.verify_evidence for that.
"""

from __future__ import annotations

from typing import Any

from app.models.hash import EvidenceHash


def generate_manifest(evidence_id: int, hashes: list[EvidenceHash]) -> dict[str, Any]:
    """Build a structured hash manifest for an evidence item.

    Args:
        evidence_id: Evidence primary key the manifest describes.
        hashes: The evidence's currently stored EvidenceHash rows.

    Returns:
        A JSON-serializable manifest dict per Master Specification Section 38.
    """
    return {
        "evidence_id": evidence_id,
        "hashes": [
            {
                "algorithm": hash_row.algorithm.value,
                "hash": hash_row.hash_value,
                "calculated_at": hash_row.calculated_at.isoformat(),
                "software_version": hash_row.software_version,
                "source_reference": hash_row.source_reference,
                "verification_status": hash_row.verification_status.value,
            }
            for hash_row in hashes
        ],
    }


def verify_manifest(manifest: dict[str, Any], hashes: list[EvidenceHash]) -> bool:
    """Check that a previously generated manifest still matches current hash rows.

    This detects manifest/database drift (e.g. an edited manifest file or a
    hash row that changed since the manifest was produced). It does not
    re-hash the underlying evidence file.

    Args:
        manifest: A manifest previously produced by `generate_manifest`.
        hashes: The evidence's current EvidenceHash rows to compare against.

    Returns:
        True if the manifest's recorded hash values match the current rows.
    """
    manifest_hashes = manifest.get("hashes")
    if not isinstance(manifest_hashes, list):
        return False

    current_by_algorithm = {hash_row.algorithm.value: hash_row.hash_value for hash_row in hashes}
    manifest_by_algorithm: dict[str, str] = {}
    for entry in manifest_hashes:
        if not isinstance(entry, dict):
            return False
        algorithm = entry.get("algorithm")
        hash_value = entry.get("hash")
        if not isinstance(algorithm, str) or not isinstance(hash_value, str):
            return False
        if algorithm in manifest_by_algorithm:
            return False
        manifest_by_algorithm[algorithm] = hash_value

    if manifest_by_algorithm.keys() != current_by_algorithm.keys():
        return False

    return all(
        manifest_by_algorithm[algorithm].lower() == current_value.lower()
        for algorithm, current_value in current_by_algorithm.items()
    )
