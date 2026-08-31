"""API tests for the Phase 15/16 audit/provenance routes:
`GET /api/v1/cases/{case_id}/audit`, `GET /api/v1/evidence/{evidence_id}/custody`,
`GET /api/v1/cases/{case_id}/audit/verify`.
"""

from __future__ import annotations

from sqlalchemy import text

from app.audit import ActorType, ProcessingOperation
from app.core.case_manager import CaseManager
from app.core.provenance_manager import ProvenanceManager
from app.models import Case, Evidence, JobStatus
from app.schemas.case import CaseCreateRequest


def _make_case(test_db, case_id: str = "API-AUDIT-CASE-1") -> Case:
    return CaseManager.create_case(
        test_db, CaseCreateRequest(case_id=case_id, name="API audit case")
    )


def _make_evidence(test_db, case: Case) -> Evidence:
    evidence = Evidence(evidence_id=f"EVID-{case.case_id}", case_id=case.id, source_type="cp_plus")
    test_db.add(evidence)
    test_db.commit()
    test_db.refresh(evidence)
    return evidence


def test_get_case_audit_returns_recorded_events(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    evidence = _make_evidence(test_db, case)
    ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.PARSING.value,
        actor="CPPlusParser",
        actor_type=ActorType.SYSTEM,
        tool="CPPlusParser",
        tool_version="0.2.0",
        status=JobStatus.COMPLETED,
    )

    response = test_client.get(
        f"/api/v1/cases/{case.id}/audit", headers=make_authenticated_headers()
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["operation"] == "parsing"
    assert data[0]["actor_type"] == "system"
    assert data[0]["tool_version"] == "0.2.0"
    # Phase 16: sealed into the hash chain at creation time.
    assert data[0]["previous_hash"] is not None
    assert data[0]["current_hash"] is not None


def test_get_case_audit_missing_case_returns_404(test_client, make_authenticated_headers) -> None:
    response = test_client.get("/api/v1/cases/999999/audit", headers=make_authenticated_headers())
    assert response.status_code == 404


def test_get_evidence_custody_returns_recorded_events(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    evidence = _make_evidence(test_db, case)
    ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation="evidence_registered",
        actor="Examiner",
        actor_type=ActorType.HUMAN,
        status=JobStatus.COMPLETED,
    )

    response = test_client.get(
        f"/api/v1/evidence/{evidence.id}/custody", headers=make_authenticated_headers()
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["operation"] == "evidence_registered"
    assert data[0]["actor_type"] == "human"


def test_get_evidence_custody_missing_evidence_returns_404(
    test_client, make_authenticated_headers
) -> None:
    response = test_client.get(
        "/api/v1/evidence/999999/custody", headers=make_authenticated_headers()
    )
    assert response.status_code == 404


def test_case_audit_never_includes_a_blockchain_anchor_field(
    test_client, test_db, make_authenticated_headers
) -> None:
    """Phase 17 boundary: no anchor-related field leaks into the response shape."""
    case = _make_case(test_db)
    ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        operation=ProcessingOperation.CORRELATION.value,
        actor="CorrelationEngine",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )
    response = test_client.get(
        f"/api/v1/cases/{case.id}/audit", headers=make_authenticated_headers()
    )
    blob = str(response.json()).lower()
    for forbidden in ("blockchain", "anchor", "transaction_reference"):
        assert forbidden not in blob


def test_verify_case_audit_chain_valid(test_client, test_db, make_authenticated_headers) -> None:
    case = _make_case(test_db)
    ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        operation=ProcessingOperation.PARSING.value,
        actor="CPPlusParser",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )
    ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        operation=ProcessingOperation.EXTRACTION.value,
        actor="RecordingManager",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )

    response = test_client.get(
        f"/api/v1/cases/{case.id}/audit/verify", headers=make_authenticated_headers()
    )

    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case.id
    assert data["chain_scope"] == "case"
    assert data["valid"] is True
    assert data["event_count"] == 2
    assert data["failure"] is None


def test_verify_case_audit_chain_empty_case_is_valid(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    response = test_client.get(
        f"/api/v1/cases/{case.id}/audit/verify", headers=make_authenticated_headers()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["event_count"] == 0


def test_verify_case_audit_chain_detects_tampering(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        operation=ProcessingOperation.PARSING.value,
        actor="CPPlusParser",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )
    event = ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        operation=ProcessingOperation.EXTRACTION.value,
        actor="RecordingManager",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )

    # Directly tamper with a persisted event's status, bypassing the
    # append-only API surface entirely.
    tampered_id = event.id
    test_db.execute(
        text("UPDATE processing_events SET status = 'failed' WHERE id = :id"),
        {"id": tampered_id},
    )
    test_db.commit()

    response = test_client.get(
        f"/api/v1/cases/{case.id}/audit/verify", headers=make_authenticated_headers()
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["failure"]["event_id"] == tampered_id
    assert data["failure"]["reason"] == "current_hash_mismatch"


def test_verify_case_audit_chain_missing_case_returns_404(
    test_client, make_authenticated_headers
) -> None:
    response = test_client.get(
        "/api/v1/cases/999999/audit/verify", headers=make_authenticated_headers()
    )
    assert response.status_code == 404
