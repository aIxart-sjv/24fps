"""
Tests for the evidence integrity hashing service layer and API routes.
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy.exc import IntegrityError

from app.integrity.hash_verification import IntegrityManager
from app.models import Case, CaseStatus, Evidence, EvidenceHash, VerificationStatus


def _make_case_and_evidence(test_db, case_id: str, evidence_id: str, source_path):
    case = Case(case_id=case_id, name="Integrity Test Case", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(
        evidence_id=evidence_id,
        case_id=case.id,
        source_type="forensic_image",
        source_path=str(source_path),
    )
    test_db.add(evidence)
    test_db.commit()
    return case, evidence


@pytest.fixture
def evidence_file(tmp_path):
    content = b"integrity test evidence bytes"
    path = tmp_path / "evidence.dd"
    path.write_bytes(content)
    return path, content


def test_hash_evidence_creates_sha256_and_md5(test_db, evidence_file):
    path, content = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-001", "E001", path)

    hashes = IntegrityManager.hash_evidence(test_db, evidence.id)

    assert len(hashes) == 2
    algorithms = {h.algorithm.value for h in hashes}
    assert algorithms == {"sha256", "md5"}
    for hash_row in hashes:
        assert hash_row.verification_status == VerificationStatus.NOT_VERIFIED

    sha256_row = next(h for h in hashes if h.algorithm.value == "sha256")
    assert sha256_row.hash_value == hashlib.sha256(content).hexdigest()


def test_hash_evidence_missing_evidence_raises(test_db):
    with pytest.raises(ValueError):
        IntegrityManager.hash_evidence(test_db, 99999)


def test_hash_evidence_without_source_path_raises(test_db):
    case = Case(case_id="INT-002", name="No Source Path", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()
    evidence = Evidence(evidence_id="E002", case_id=case.id, source_type="forensic_image")
    test_db.add(evidence)
    test_db.commit()

    with pytest.raises(ValueError):
        IntegrityManager.hash_evidence(test_db, evidence.id)


def test_hash_evidence_missing_file_raises(test_db, tmp_path):
    missing_path = tmp_path / "does_not_exist.dd"
    _case, evidence = _make_case_and_evidence(test_db, "INT-003", "E003", missing_path)

    with pytest.raises(FileNotFoundError):
        IntegrityManager.hash_evidence(test_db, evidence.id)


def test_hash_evidence_twice_raises(test_db, evidence_file):
    path, _ = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-004", "E004", path)

    IntegrityManager.hash_evidence(test_db, evidence.id)
    with pytest.raises(ValueError):
        IntegrityManager.hash_evidence(test_db, evidence.id)


def test_verify_evidence_matches(test_db, evidence_file):
    path, _ = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-005", "E005", path)

    IntegrityManager.hash_evidence(test_db, evidence.id)
    verified = IntegrityManager.verify_evidence(test_db, evidence.id)

    assert all(h.verification_status == VerificationStatus.VERIFIED for h in verified)


def test_verify_evidence_detects_tampering(test_db, evidence_file):
    path, _ = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-006", "E006", path)

    IntegrityManager.hash_evidence(test_db, evidence.id)

    path.write_bytes(b"tampered content, different from original")
    verified = IntegrityManager.verify_evidence(test_db, evidence.id)

    assert all(h.verification_status == VerificationStatus.MISMATCH for h in verified)


def test_verify_evidence_without_hashes_raises(test_db, evidence_file):
    path, _ = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-007", "E007", path)

    with pytest.raises(ValueError):
        IntegrityManager.verify_evidence(test_db, evidence.id)


def test_list_evidence_hashes(test_db, evidence_file):
    path, _ = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-008", "E008", path)

    IntegrityManager.hash_evidence(test_db, evidence.id)
    hashes = IntegrityManager.list_evidence_hashes(test_db, evidence.id)

    assert len(hashes) == 2


def test_list_evidence_hashes_missing_evidence_raises(test_db):
    with pytest.raises(ValueError):
        IntegrityManager.list_evidence_hashes(test_db, 99999)


def test_evidence_hash_unique_constraint(test_db, evidence_file):
    """Two hash rows for the same evidence+algorithm must be rejected."""
    path, _ = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-009", "E009", path)

    test_db.add(EvidenceHash(evidence_id=evidence.id, algorithm="sha256", hash_value="a" * 64))
    test_db.commit()

    test_db.add(EvidenceHash(evidence_id=evidence.id, algorithm="sha256", hash_value="b" * 64))
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


# --- API tests ---


def test_hash_evidence_api(test_client, test_db, evidence_file):
    path, _content = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-API-001", "E-API-001", path)

    response = test_client.post(f"/api/v1/evidence/{evidence.id}/hash")
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 2
    algorithms = {row["algorithm"] for row in data}
    assert algorithms == {"sha256", "md5"}


def test_hash_evidence_api_not_found(test_client):
    response = test_client.post("/api/v1/evidence/99999/hash")
    assert response.status_code == 400


def test_verify_evidence_api(test_client, test_db, evidence_file):
    path, _ = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-API-002", "E-API-002", path)

    test_client.post(f"/api/v1/evidence/{evidence.id}/hash")
    response = test_client.post(f"/api/v1/evidence/{evidence.id}/verify")
    assert response.status_code == 200
    data = response.json()
    assert all(row["verification_status"] == "verified" for row in data)


def test_verify_evidence_api_without_hashes(test_client, test_db, evidence_file):
    path, _ = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-API-003", "E-API-003", path)

    response = test_client.post(f"/api/v1/evidence/{evidence.id}/verify")
    assert response.status_code == 400


def test_list_evidence_hashes_api(test_client, test_db, evidence_file):
    path, _ = evidence_file
    _case, evidence = _make_case_and_evidence(test_db, "INT-API-004", "E-API-004", path)

    test_client.post(f"/api/v1/evidence/{evidence.id}/hash")
    response = test_client.get(f"/api/v1/evidence/{evidence.id}/hashes")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_evidence_hashes_api_not_found(test_client):
    response = test_client.get("/api/v1/evidence/99999/hashes")
    assert response.status_code == 404
