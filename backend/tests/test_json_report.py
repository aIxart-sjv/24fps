"""Pure tests for app/reporting/json_report.py (Phase 18). No database --
built directly against hand-built `ReportData`.
"""

from __future__ import annotations

import json

from app.reporting.evidence_report import (
    AISection,
    AuditChainSection,
    CaseSummarySection,
    LimitationEntry,
    ReportData,
    ReportMetadata,
)
from app.reporting.json_report import render_json


def _minimal_data() -> ReportData:
    meta = ReportMetadata(
        report_schema_version="1.0",
        software_version="0.1.0",
        generated_at="2026-01-01T00:00:00+00:00",
        case_id=1,
        case_identifier="CASE-1",
    )
    case = CaseSummarySection(
        case_id=1,
        case_identifier="CASE-1",
        case_number=None,
        name="Test",
        description=None,
        examiner=None,
        status="active",
        created_at=None,
        updated_at=None,
        evidence_count=0,
        recording_count=0,
        recovery_result_count=0,
        ai_result_count=0,
        ai_track_count=0,
        motion_event_count=0,
        validation_metric_count=0,
        correlation_event_count=0,
        timeline_event_count=0,
        processing_event_count=0,
        blockchain_anchor_count=0,
        report_count=0,
    )
    audit = AuditChainSection(
        chain_id="case-1",
        chain_scope="case",
        chain_algorithm="sha256",
        event_count=0,
        first_event_id=None,
        last_event_id=None,
        valid=True,
        failure_event_id=None,
        failure_reason=None,
        failure_detail=None,
        checked_at="2026-01-01T00:00:00+00:00",
    )
    return ReportData(
        metadata=meta,
        case=case,
        evidence=[],
        acquisition=[],
        identification=[],
        recordings=[],
        recovery=[],
        timeline=[],
        correlation=[],
        ai=AISection(),
        validation=[],
        provenance=[],
        audit=audit,
        blockchain=[],
        limitations=[LimitationEntry(category="test", description="a limitation")],
    )


def test_render_json_is_deterministic() -> None:
    data = _minimal_data()
    assert render_json(data) == render_json(data)


def test_render_json_is_valid_json_with_expected_top_level_keys() -> None:
    data = _minimal_data()
    parsed = json.loads(render_json(data))
    assert set(parsed.keys()) == {
        "metadata",
        "case",
        "evidence",
        "acquisition",
        "identification",
        "recordings",
        "recovery",
        "timeline",
        "correlation",
        "ai",
        "validation",
        "provenance",
        "audit",
        "blockchain",
        "findings",
        "limitations",
    }


def test_render_json_top_level_key_order_matches_section_order() -> None:
    data = _minimal_data()
    parsed = json.loads(render_json(data))
    assert list(parsed.keys())[0] == "metadata"
    assert list(parsed.keys())[-1] == "limitations"


def test_render_json_includes_schema_version() -> None:
    data = _minimal_data()
    parsed = json.loads(render_json(data))
    assert parsed["metadata"]["report_schema_version"] == "1.0"
    assert parsed["metadata"]["software_version"] == "0.1.0"


def test_render_json_never_includes_python_repr_artifacts() -> None:
    data = _minimal_data()
    text = render_json(data).decode("utf-8")
    assert "0x" not in text  # no memory addresses
    assert "object at" not in text


def test_render_json_limitations_never_suppressed() -> None:
    data = _minimal_data()
    parsed = json.loads(render_json(data))
    assert len(parsed["limitations"]) == 1
    assert parsed["limitations"][0]["category"] == "test"


def test_render_json_is_utf8_and_ascii_safe() -> None:
    data = _minimal_data()
    raw = render_json(data)
    # Round-trips cleanly as strict UTF-8/ASCII-safe JSON.
    raw.decode("ascii")
    json.loads(raw)


def test_render_json_changes_when_content_changes() -> None:
    data1 = _minimal_data()
    import dataclasses

    data2 = dataclasses.replace(data1, case=dataclasses.replace(data1.case, name="Different Name"))
    assert render_json(data1) != render_json(data2)
