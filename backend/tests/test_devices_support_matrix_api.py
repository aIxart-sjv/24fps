"""Tests for GET /devices/support-matrix (Phase 23)."""

from __future__ import annotations


def test_support_matrix_lists_every_registered_vendor(test_client) -> None:
    resp = test_client.get("/api/v1/devices/support-matrix")
    assert resp.status_code == 200
    body = resp.json()
    vendors = {row["vendor"] for row in body}
    assert "CP Plus" in vendors
    assert "Dahua Technology" in vendors
    assert "Hikvision" in vendors


def test_support_matrix_reports_honest_support_levels(test_client) -> None:
    resp = test_client.get("/api/v1/devices/support-matrix")
    body = resp.json()
    by_vendor = {row["vendor"]: row for row in body}

    # CP Plus is the only Level-4-validated vendor in this codebase --
    # never falsely reported as fully supported for every vendor.
    assert by_vendor["CP Plus"]["support_level"] == 4
    assert by_vendor["Dahua Technology"]["support_level"] < 4
    for row in body:
        assert row["evidence_basis"], f"{row['vendor']} has no evidence basis listed"
