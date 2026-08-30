"""
Service layer for evidence integrity hashing and verification.
Master Specification Section 38 (Integrity Engine).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrity.evidence_fingerprint import compute_evidence_fingerprint
from app.models import Evidence, EvidenceHash, HashAlgorithm, VerificationStatus


class IntegrityManager:
    """Service layer for computing and verifying evidence integrity hashes."""

    @staticmethod
    def hash_evidence(db: Session, evidence_id: int) -> list[EvidenceHash]:
        """Compute and store the initial SHA-256 and MD5 hashes for evidence.

        Args:
            db: Database session.
            evidence_id: Evidence primary key.

        Returns:
            The created EvidenceHash rows.

        Raises:
            ValueError: If evidence is not found, has no source_path, or
                already has hashes recorded.
            FileNotFoundError: If the evidence source file does not exist.
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence with id {evidence_id} not found")

        if not evidence.source_path:
            raise ValueError(f"Evidence with id {evidence_id} has no source_path to hash")

        existing = db.query(EvidenceHash).filter(EvidenceHash.evidence_id == evidence_id).first()
        if existing:
            raise ValueError(
                f"Evidence with id {evidence_id} already has hashes recorded; "
                "use verify to re-check integrity"
            )

        source_path = Path(evidence.source_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"Evidence source file not found: {source_path}")

        fingerprint = compute_evidence_fingerprint(source_path)
        software_version = get_settings().app_version

        hashes = [
            EvidenceHash(
                evidence_id=evidence_id,
                algorithm=HashAlgorithm.SHA256,
                hash_value=fingerprint.sha256,
                software_version=software_version,
                source_reference=evidence.source_path,
                verification_status=VerificationStatus.NOT_VERIFIED,
            ),
            EvidenceHash(
                evidence_id=evidence_id,
                algorithm=HashAlgorithm.MD5,
                hash_value=fingerprint.md5,
                software_version=software_version,
                source_reference=evidence.source_path,
                verification_status=VerificationStatus.NOT_VERIFIED,
            ),
        ]
        db.add_all(hashes)
        db.commit()
        for hash_row in hashes:
            db.refresh(hash_row)
        return hashes

    @staticmethod
    def verify_evidence(db: Session, evidence_id: int) -> list[EvidenceHash]:
        """Recompute evidence hashes and compare them against stored values.

        Args:
            db: Database session.
            evidence_id: Evidence primary key.

        Returns:
            The updated EvidenceHash rows with refreshed verification_status.

        Raises:
            ValueError: If evidence is not found or has no recorded hashes.
            FileNotFoundError: If the evidence source file does not exist.
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence with id {evidence_id} not found")

        existing = db.query(EvidenceHash).filter(EvidenceHash.evidence_id == evidence_id).all()
        if not existing:
            raise ValueError(
                f"Evidence with id {evidence_id} has no recorded hashes; call hash first"
            )

        if not evidence.source_path:
            raise ValueError(f"Evidence with id {evidence_id} has no source_path to verify")

        source_path = Path(evidence.source_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"Evidence source file not found: {source_path}")

        fingerprint = compute_evidence_fingerprint(source_path)
        recomputed = {
            HashAlgorithm.SHA256: fingerprint.sha256,
            HashAlgorithm.MD5: fingerprint.md5,
        }

        for hash_row in existing:
            recomputed_value = recomputed.get(hash_row.algorithm)
            if recomputed_value is None:
                continue
            if recomputed_value.lower() == hash_row.hash_value.lower():
                hash_row.verification_status = VerificationStatus.VERIFIED
            else:
                hash_row.verification_status = VerificationStatus.MISMATCH

        db.commit()
        for hash_row in existing:
            db.refresh(hash_row)
        return existing

    @staticmethod
    def list_evidence_hashes(db: Session, evidence_id: int) -> list[EvidenceHash]:
        """List all stored hashes for an evidence item.

        Args:
            db: Database session.
            evidence_id: Evidence primary key.

        Returns:
            List of EvidenceHash rows, empty if none recorded.

        Raises:
            ValueError: If evidence is not found.
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence with id {evidence_id} not found")
        return db.query(EvidenceHash).filter(EvidenceHash.evidence_id == evidence_id).all()
