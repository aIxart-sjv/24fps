"""API tests for the Phase 17 blockchain routes:
`POST /api/v1/cases/{case_id}/blockchain/anchor`,
`GET /api/v1/cases/{case_id}/blockchain/anchors`,
`POST /api/v1/blockchain/verify`.

The API layer resolves its `BlockchainProvider` from `BLOCKCHAIN_PROVIDER`/
`BLOCKCHAIN_NETWORK` settings (never a directly-injected test double, to
also exercise the config-driven factory path end-to-end) -- these tests
set `BLOCKCHAIN_PROVIDER=local_testnet` via monkeypatch, matching the
pattern used for evidence/artifact roots in the Phase 15 real-evidence
integration test.
"""

from __future__ import annotations

import pytest

from app.audit import ActorType, ProcessingOperation
from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.provenance_manager import ProvenanceManager
from app.models import Case, JobStatus
from app.schemas.case import CaseCreateRequest


@pytest.fixture(autouse=True)
def _local_testnet_provider(monkeypatch: pytest.MonkeyPatch):
    """Every test in this file gets a fresh, isolated local/test
    provider network name so the module-level provider singleton
    (keyed by network) never leaks state between tests."""
    network_name = f"unit-test-{id(monkeypatch)}"
    monkeypatch.setenv("BLOCKCHAIN_PROVIDER", "local_testnet")
    monkeypatch.setenv("BLOCKCHAIN_NETWORK", network_name)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_case(test_db, case_id: str = "API-CHAIN-CASE-1") -> Case:
    return CaseManager.create_case(test_db, CaseCreateRequest(case_id=case_id, name="Chain API"))


def _record(test_db, case: Case, operation: str) -> None:
    ProvenanceManager.record_event(
        test_db,
        case_id=case.id,
        operation=operation,
        actor="TestActor",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )


def test_create_anchor_endpoint(test_client, test_db, make_authenticated_headers) -> None:
    case = _make_case(test_db)
    _record(test_db, case, ProcessingOperation.PARSING.value)

    response = test_client.post(
        f"/api/v1/cases/{case.id}/blockchain/anchor", json={}, headers=make_authenticated_headers()
    )

    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case.id
    assert data["chain_id"] == f"case-{case.id}"
    assert data["provider"] == "local_testnet"
    assert data["status"] == "local_test"
    assert data["transaction_reference"].startswith("LOCAL-TEST-ANCHOR-")
    assert len(data["audit_state_hash"]) == 64
    assert data["verified_at"] is None


def test_create_anchor_with_reason(test_client, test_db, make_authenticated_headers) -> None:
    case = _make_case(test_db)
    _record(test_db, case, ProcessingOperation.PARSING.value)

    response = test_client.post(
        f"/api/v1/cases/{case.id}/blockchain/anchor",
        json={"reason": "case_closure"},
        headers=make_authenticated_headers(),
    )

    assert response.status_code == 200
    assert response.json()["reason"] == "case_closure"


def test_create_anchor_missing_case_returns_404(test_client, make_authenticated_headers) -> None:
    response = test_client.post(
        "/api/v1/cases/999999/blockchain/anchor", json={}, headers=make_authenticated_headers()
    )
    assert response.status_code == 404


def test_create_anchor_empty_chain_returns_400(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    response = test_client.post(
        f"/api/v1/cases/{case.id}/blockchain/anchor", json={}, headers=make_authenticated_headers()
    )
    assert response.status_code == 400


def test_list_anchors_endpoint(test_client, test_db, make_authenticated_headers) -> None:
    case = _make_case(test_db)
    _record(test_db, case, ProcessingOperation.PARSING.value)
    test_client.post(
        f"/api/v1/cases/{case.id}/blockchain/anchor", json={}, headers=make_authenticated_headers()
    )

    _record(test_db, case, ProcessingOperation.EXTRACTION.value)
    test_client.post(
        f"/api/v1/cases/{case.id}/blockchain/anchor", json={}, headers=make_authenticated_headers()
    )

    response = test_client.get(
        f"/api/v1/cases/{case.id}/blockchain/anchors", headers=make_authenticated_headers()
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] < data[1]["id"]


def test_list_anchors_missing_case_returns_404(test_client, make_authenticated_headers) -> None:
    response = test_client.get(
        "/api/v1/cases/999999/blockchain/anchors", headers=make_authenticated_headers()
    )
    assert response.status_code == 404


def test_verify_endpoint_valid(test_client, test_db, make_authenticated_headers) -> None:
    case = _make_case(test_db)
    _record(test_db, case, ProcessingOperation.PARSING.value)
    create_response = test_client.post(
        f"/api/v1/cases/{case.id}/blockchain/anchor", json={}, headers=make_authenticated_headers()
    )
    anchor_id = create_response.json()["id"]

    response = test_client.post(
        "/api/v1/blockchain/verify",
        json={"anchor_id": anchor_id},
        headers=make_authenticated_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["outcome"] == "valid"
    assert data["chain_failure"] is None


def test_verify_endpoint_detects_local_tamper(
    test_client, test_db, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    _record(test_db, case, ProcessingOperation.PARSING.value)
    create_response = test_client.post(
        f"/api/v1/cases/{case.id}/blockchain/anchor", json={}, headers=make_authenticated_headers()
    )
    anchor_id = create_response.json()["id"]

    from app.models import ProcessingEvent

    row = (
        test_db.query(ProcessingEvent)
        .filter(ProcessingEvent.case_id == case.id, ProcessingEvent.operation == "parsing")
        .first()
    )
    row.status = "failed"
    test_db.commit()

    response = test_client.post(
        "/api/v1/blockchain/verify",
        json={"anchor_id": anchor_id},
        headers=make_authenticated_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["outcome"] == "chain_invalid"
    assert data["chain_valid"] is False
    assert data["chain_failure"] is not None


def test_verify_endpoint_missing_anchor_returns_404(
    test_client, make_authenticated_headers
) -> None:
    response = test_client.post(
        "/api/v1/blockchain/verify",
        json={"anchor_id": 999999},
        headers=make_authenticated_headers(),
    )
    assert response.status_code == 404


def test_blockchain_response_never_includes_a_report_field(
    test_client, test_db, make_authenticated_headers
) -> None:
    """Phase 18 boundary: no report-generation field leaks into the
    blockchain response shape."""
    case = _make_case(test_db)
    _record(test_db, case, ProcessingOperation.PARSING.value)
    response = test_client.post(
        f"/api/v1/cases/{case.id}/blockchain/anchor", json={}, headers=make_authenticated_headers()
    )
    blob = str(response.json()).lower()
    for forbidden in ("report_path", "pdf", "forensic_report"):
        assert forbidden not in blob
