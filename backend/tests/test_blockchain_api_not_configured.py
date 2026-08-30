"""API test for the Phase 17 blockchain routes with the *default*
configuration (`BLOCKCHAIN_PROVIDER=none`) -- confirms blockchain
anchoring is a controlled, observable 503 when unconfigured, never a
silent success or a crash, and that Phase 16 audit/provenance endpoints
remain fully usable regardless (Master Specification Section 42: "The
project must remain usable if blockchain infrastructure is
unavailable").

Deliberately in its own module (not `test_blockchain_api.py`, which
opts every test into a working local/test provider via an autouse
fixture) so the default-disabled path gets its own explicit coverage.
"""

from __future__ import annotations

from app.audit import ActorType, ProcessingOperation
from app.core.case_manager import CaseManager
from app.core.provenance_manager import ProvenanceManager
from app.models import Case, JobStatus
from app.schemas.case import CaseCreateRequest


def _make_case(test_db, case_id: str = "API-CHAIN-NOCONFIG-1") -> Case:
    return CaseManager.create_case(test_db, CaseCreateRequest(case_id=case_id, name="No config"))


def test_create_anchor_with_no_provider_configured_returns_503(test_client, test_db) -> None:
    case = _make_case(test_db)
    ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        operation=ProcessingOperation.PARSING.value,
        actor="TestActor",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )

    response = test_client.post(f"/api/v1/cases/{case.id}/blockchain/anchor", json={})

    assert response.status_code == 503


def test_audit_endpoints_still_work_without_blockchain_configured(test_client, test_db) -> None:
    """Phase 16 local hash-chain integrity is independent of blockchain
    availability (Master Specification Section 42's closing rule)."""
    case = _make_case(test_db)
    ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        operation=ProcessingOperation.PARSING.value,
        actor="TestActor",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )

    audit_response = test_client.get(f"/api/v1/cases/{case.id}/audit")
    assert audit_response.status_code == 200
    assert len(audit_response.json()) == 1

    verify_response = test_client.get(f"/api/v1/cases/{case.id}/audit/verify")
    assert verify_response.status_code == 200
    assert verify_response.json()["valid"] is True
