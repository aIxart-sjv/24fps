"""Tests for app/core/findings_engine.py (Phase 22)."""

from __future__ import annotations

import json

from app.core.case_manager import CaseManager
from app.core.findings_engine import FindingsEngine
from app.models import Finding, FindingConfidence, FindingSeverity, FindingStatus, FindingType
from app.schemas.case import CaseCreateRequest


def _make_case(db, case_id: str = "CASE-FIND-1"):
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Findings test"))


def test_upsert_finding_creates_new_finding(test_db) -> None:
    case = _make_case(test_db)
    finding, is_new = FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.INTEGRITY_MISMATCH,
        severity=FindingSeverity.HIGH,
        confidence=FindingConfidence.VERIFIED,
        title="Test finding",
        description="A test description.",
    )
    assert is_new is True
    assert finding.status == FindingStatus.OPEN.value
    assert finding.occurrence_count == 1


def test_upsert_finding_merges_into_existing_open_finding(test_db) -> None:
    case = _make_case(test_db)
    first, _ = FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.PARTIAL_RECOVERY,
        severity=FindingSeverity.MEDIUM,
        confidence=FindingConfidence.VERIFIED,
        title="Partial recovery",
        description="First occurrence.",
        recording_id=7,
        source_reference={"recovery_result_id": 1},
    )
    second, is_new = FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.PARTIAL_RECOVERY,
        severity=FindingSeverity.MEDIUM,
        confidence=FindingConfidence.VERIFIED,
        title="Partial recovery",
        description="Second occurrence.",
        recording_id=7,
        source_reference={"recovery_result_id": 2},
    )
    assert is_new is False
    assert second.id == first.id
    assert second.occurrence_count == 2
    assert test_db.query(Finding).count() == 1
    ref = json.loads(second.source_reference)
    assert ref["recovery_result_id"] == [1, 2]


def test_upsert_finding_never_merges_into_a_resolved_finding(test_db) -> None:
    case = _make_case(test_db)
    finding, _ = FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.UNSUPPORTED_FORMAT,
        severity=FindingSeverity.MEDIUM,
        confidence=FindingConfidence.NOT_APPLICABLE,
        title="Unsupported",
        description="First.",
        evidence_id=3,
    )
    finding.status = FindingStatus.RESOLVED.value
    test_db.add(finding)
    test_db.commit()

    _new_finding, is_new = FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.UNSUPPORTED_FORMAT,
        severity=FindingSeverity.MEDIUM,
        confidence=FindingConfidence.NOT_APPLICABLE,
        title="Unsupported",
        description="Second, after resolution.",
        evidence_id=3,
    )
    assert is_new is True
    assert test_db.query(Finding).count() == 2


def test_upsert_finding_raises_severity_but_never_lowers_it(test_db) -> None:
    case = _make_case(test_db)
    FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.RECOVERY_WARNING,
        severity=FindingSeverity.LOW,
        confidence=FindingConfidence.PARTIAL,
        title="Recovery warning",
        description="Low severity first.",
        recording_id=9,
    )
    updated, _ = FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.RECOVERY_WARNING,
        severity=FindingSeverity.INFO,
        confidence=FindingConfidence.PARTIAL,
        title="Recovery warning",
        description="Lower severity second occurrence.",
        recording_id=9,
    )
    assert updated.severity == FindingSeverity.LOW.value


def test_list_case_findings_orders_unresolved_and_severity_first(test_db) -> None:
    case = _make_case(test_db)
    low, _ = FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.RECOVERY_WARNING,
        severity=FindingSeverity.LOW,
        confidence=FindingConfidence.PARTIAL,
        title="Low",
        description="low severity",
        recording_id=1,
    )
    critical, _ = FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.AUDIT_CHAIN_INVALID,
        severity=FindingSeverity.CRITICAL,
        confidence=FindingConfidence.VERIFIED,
        title="Critical",
        description="critical severity",
    )
    resolved, _ = FindingsEngine.upsert_finding(
        test_db,
        case_id=case.id,
        finding_type=FindingType.RECOVERY_WARNING,
        severity=FindingSeverity.HIGH,
        confidence=FindingConfidence.PARTIAL,
        title="Resolved high",
        description="high but resolved",
        recording_id=2,
    )
    resolved.status = FindingStatus.RESOLVED.value
    test_db.add(resolved)
    test_db.commit()

    ordered = FindingsEngine.list_case_findings(test_db, case.id)
    ordered_ids = [f.id for f in ordered]
    assert ordered_ids.index(critical.id) < ordered_ids.index(low.id)
    assert ordered_ids.index(low.id) < ordered_ids.index(resolved.id)
