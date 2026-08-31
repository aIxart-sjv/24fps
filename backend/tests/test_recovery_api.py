"""Tests for app/api/routes/recovery.py (Phase 24)."""

from __future__ import annotations

from app.adapters.cp_plus.recovery import DELETED_RECOVERY_NOT_VALIDATED_STATEMENT
from app.core.case_manager import CaseManager
from app.models import Evidence, Recording, RecoveryResult
from app.schemas.case import CaseCreateRequest


def _make_case_evidence_recording(db, suffix: str) -> Recording:
    case = CaseManager.create_case(
        db, CaseCreateRequest(case_id=f"CASE-REC-{suffix}", name="Recovery API test")
    )
    evidence = Evidence(evidence_id=f"EV-{suffix}", case_id=case.id, source_type="native_export")
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    recording = Recording(evidence_id=evidence.id, recording_id=f"REC-{suffix}")
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return recording


def test_recovery_result_surfaces_deleted_recovery_validation_warning(
    test_db, test_client, make_authenticated_headers
) -> None:
    """Phase 24 task scope, "Recovery UI -- Honest Status": the
    framework-only, unvalidated deleted-record-recovery path must carry a
    structured, prominent `validation_warning` -- not buried indistinctly
    inside `notes`."""
    recording = _make_case_evidence_recording(test_db, "1")
    result = RecoveryResult(
        evidence_id=recording.evidence_id,
        recording_id=recording.id,
        method="filesystem_index",
        status="unsupported",
        notes="final: filesystem_index -> unsupported: no index found",
    )
    test_db.add(result)
    test_db.commit()

    resp = test_client.get(
        f"/api/v1/evidence/{recording.evidence_id}/recovery-results",
        headers=make_authenticated_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["validation_warning"] == DELETED_RECOVERY_NOT_VALIDATED_STATEMENT


def test_recovery_result_omits_validation_warning_for_validated_recovery(
    test_db, test_client, make_authenticated_headers
) -> None:
    """A real, validated recovery method must never carry the
    deleted-record-recovery caution."""
    recording = _make_case_evidence_recording(test_db, "2")
    result = RecoveryResult(
        evidence_id=recording.evidence_id,
        recording_id=recording.id,
        method="vendor_damaged_recovery",
        status="recovered",
        notes="final: vendor_damaged_recovery -> recovered: clean",
    )
    test_db.add(result)
    test_db.commit()

    resp = test_client.get(
        f"/api/v1/evidence/{recording.evidence_id}/recovery-results",
        headers=make_authenticated_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["validation_warning"] is None
