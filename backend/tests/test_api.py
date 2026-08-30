"""
Tests for API endpoints.
"""

from __future__ import annotations

from app.models import Case, CaseStatus, Evidence


def test_health_endpoint(test_client):
    """Test GET /api/v1/health."""
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database_connected" in data


def test_system_info_endpoint(test_client):
    """Test GET /api/v1/system/info."""
    response = test_client.get("/api/v1/system/info")
    assert response.status_code == 200
    data = response.json()
    assert "app_version" in data
    assert "app_env" in data


def test_system_capabilities_endpoint(test_client):
    """Test GET /api/v1/system/capabilities."""
    response = test_client.get("/api/v1/system/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "subsystems" in data
    assert len(data["subsystems"]) > 0


def test_create_case(test_client):
    """Test POST /api/v1/cases."""
    request_data = {
        "case_id": "NTRO-2026-001",
        "name": "Test Investigation",
        "examiner": "John Doe",
    }
    response = test_client.post("/api/v1/cases", json=request_data)
    assert response.status_code == 201
    data = response.json()
    assert data["case_id"] == "NTRO-2026-001"
    assert data["name"] == "Test Investigation"
    assert data["status"] == "draft"


def test_create_case_duplicate_case_id(test_client, test_db):
    """Test creating case with duplicate case_id fails."""
    case = Case(case_id="UNIQUE-001", name="First", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    request_data = {
        "case_id": "UNIQUE-001",
        "name": "Duplicate",
    }
    response = test_client.post("/api/v1/cases", json=request_data)
    assert response.status_code == 400


def test_list_cases(test_client, test_db):
    """Test GET /api/v1/cases."""
    case1 = Case(case_id="LIST-001", name="Case 1", status=CaseStatus.DRAFT)
    case2 = Case(case_id="LIST-002", name="Case 2", status=CaseStatus.ACTIVE)
    test_db.add_all([case1, case2])
    test_db.commit()

    response = test_client.get("/api/v1/cases")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_get_case(test_client, test_db):
    """Test GET /api/v1/cases/{case_id}."""
    case = Case(case_id="GET-001", name="Get Test", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    response = test_client.get(f"/api/v1/cases/{case.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == "GET-001"


def test_get_case_not_found(test_client):
    """Test GET /api/v1/cases/{case_id} with invalid ID."""
    response = test_client.get("/api/v1/cases/99999")
    assert response.status_code == 404


def test_update_case(test_client, test_db):
    """Test PATCH /api/v1/cases/{case_id}."""
    case = Case(case_id="UPDATE-001", name="Original", status=CaseStatus.DRAFT)
    test_db.add(case)
    test_db.commit()

    request_data = {"name": "Updated", "status": "active"}
    response = test_client.patch(f"/api/v1/cases/{case.id}", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated"


def test_register_evidence(test_client, test_db):
    """Test POST /api/v1/cases/{case_id}/evidence."""
    case = Case(case_id="EV-001", name="Evidence Test", status=CaseStatus.ACTIVE)
    test_db.add(case)
    test_db.commit()

    request_data = {
        "evidence_id": "E001",
        "source_type": "forensic_image",
    }
    response = test_client.post(f"/api/v1/cases/{case.id}/evidence", json=request_data)
    assert response.status_code == 201
    data = response.json()
    assert data["evidence_id"] == "E001"
    assert data["source_type"] == "forensic_image"


def test_register_evidence_case_not_found(test_client):
    """Test registering evidence in non-existent case."""
    request_data = {
        "evidence_id": "E002",
        "source_type": "forensic_image",
    }
    response = test_client.post("/api/v1/cases/99999/evidence", json=request_data)
    assert response.status_code == 400


def test_list_case_evidence(test_client, test_db):
    """Test GET /api/v1/cases/{case_id}/evidence."""
    case = Case(case_id="EV-002", name="Evidence List Test", status=CaseStatus.ACTIVE)
    test_db.add(case)
    test_db.commit()

    ev1 = Evidence(evidence_id="E003", case_id=case.id, source_type="forensic_image")
    ev2 = Evidence(evidence_id="E004", case_id=case.id, source_type="native_export")
    test_db.add_all([ev1, ev2])
    test_db.commit()

    response = test_client.get(f"/api/v1/cases/{case.id}/evidence")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_evidence(test_client, test_db):
    """Test GET /api/v1/evidence/{evidence_id}."""
    case = Case(case_id="EV-003", name="Get Evidence Test", status=CaseStatus.ACTIVE)
    test_db.add(case)
    test_db.commit()

    evidence = Evidence(evidence_id="E005", case_id=case.id, source_type="forensic_image")
    test_db.add(evidence)
    test_db.commit()

    response = test_client.get(f"/api/v1/evidence/{evidence.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["evidence_id"] == "E005"


def test_get_evidence_not_found(test_client):
    """Test GET /api/v1/evidence/{evidence_id} with invalid ID."""
    response = test_client.get("/api/v1/evidence/99999")
    assert response.status_code == 404
