"""Tests for app/api/routes/timeline.py (Phase 23/24)."""

from __future__ import annotations

import struct
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.cp_plus.models import (
    ADIT_MAGIC,
    OUTER_HEADER_SIZE,
    RECORD_FOOTER_MAGIC,
    RECORD_HEADER_SIZE,
    RECORD_MAGIC,
)
from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.core.timeline_manager import TimelineManager
from app.core.timestamp_manager import TimestampManager
from app.models import Case
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest

_ANNEXB_PREFIX = b"\x00" * 33


def _outer_header_bytes(start_counter: int, end_counter: int) -> bytes:
    return (
        ADIT_MAGIC
        + struct.pack("<II", start_counter, end_counter)
        + b"\x00" * (OUTER_HEADER_SIZE - 16)
    )


def _record_bytes(type_tag: int, counter: int, body: bytes) -> bytes:
    length = RECORD_HEADER_SIZE + len(body) + 8
    header = RECORD_MAGIC + struct.pack("<III", type_tag, counter, length)
    footer = RECORD_FOOTER_MAGIC + struct.pack("<I", length)
    return header + body + footer


def _nal(nal_unit_type: int) -> bytes:
    first_byte = (nal_unit_type << 1) & 0xFF
    return b"\x00\x00\x01" + bytes([first_byte, 0x01]) + b"\xff\xee"


def _synthetic_cpv_bytes(*, start_counter: int, end_counter: int) -> bytes:
    body = _ANNEXB_PREFIX + _nal(32) + _nal(33) + _nal(34) + _nal(19)
    return _outer_header_bytes(start_counter, end_counter) + _record_bytes(
        0xFD, start_counter, body
    )


def _make_case(db, case_id: str = "CASE-TL-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Timeline API test"))


def test_list_case_timeline_returns_examiner_markers(
    test_db, test_client, make_authenticated_headers
) -> None:
    case = _make_case(test_db)
    TimelineManager.create_examiner_marker(
        test_db,
        case_id=case.id,
        camera_id="CAM-1",
        recording_id=None,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        description="Examiner noted a vehicle arrival",
    )

    resp = test_client.get(
        f"/api/v1/cases/{case.id}/timeline", headers=make_authenticated_headers()
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["event_type"] == "examiner_marker"
    assert body[0]["source"] == "examiner"


def test_list_case_timeline_unknown_case_404(test_client, make_authenticated_headers) -> None:
    resp = test_client.get("/api/v1/cases/999999/timeline", headers=make_authenticated_headers())
    assert resp.status_code == 404


def test_list_case_timeline_excludes_correlated_by_default(
    test_db, test_client, make_authenticated_headers
) -> None:
    case = _make_case(test_db, "CASE-TL-2")
    resp = test_client.get(
        f"/api/v1/cases/{case.id}/timeline", headers=make_authenticated_headers()
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_case_timeline_reports_real_timestamp_status(
    test_db, test_client, monkeypatch, tmp_path: Path, make_authenticated_headers
) -> None:
    """Phase 24 task scope, "Timeline": the response must carry the real,
    persisted normalization status/source/timezone basis -- never a
    stronger claim than `TimestampManager` actually recorded, and never
    silently omitted."""
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(evidence_root))
    get_settings.cache_clear()

    case = _make_case(test_db, "CASE-TL-3")
    source_path = evidence_root / "NVR_ch1_main_20260101120000_20260101120010.cpv"
    source_path.write_bytes(_synthetic_cpv_bytes(start_counter=1, end_counter=2))
    evidence = EvidenceManager.register_evidence(
        test_db,
        case.id,
        EvidenceCreateRequest(
            evidence_id="EV-TL-1", source_type="native_export", source_path=str(source_path)
        ),
    )
    recordings = RecordingManager.enumerate_recordings(test_db, evidence.id)
    assert recordings
    TimestampManager.normalize_recording(
        test_db,
        recordings[0].id,
        source_timezone="Asia/Kolkata",
        source_timezone_basis="test basis: NVR configured for IST",
    )
    TimelineManager.ingest_recording_events(test_db, recordings[0].id)

    resp = test_client.get(
        f"/api/v1/cases/{case.id}/timeline", headers=make_authenticated_headers()
    )
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 2
    for event in events:
        assert event["recording_id"] == recordings[0].id
        assert event["timestamp_status"] == "unverified"
        assert event["timestamp_source"] == "filename_derived"
        assert event["timezone_status"] == "known"
        assert event["timezone_basis"] == "test basis: NVR configured for IST"

    get_settings.cache_clear()


def test_list_case_timeline_examiner_marker_has_unknown_timestamp_status(
    test_db, test_client, make_authenticated_headers
) -> None:
    """An event with no linked recording (e.g. an examiner marker) reports
    `timestamp_status="unknown"` -- never fabricated as verified."""
    case = _make_case(test_db, "CASE-TL-4")
    TimelineManager.create_examiner_marker(
        test_db,
        case_id=case.id,
        camera_id="CAM-1",
        recording_id=None,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        description="Examiner noted a vehicle arrival",
    )
    resp = test_client.get(
        f"/api/v1/cases/{case.id}/timeline", headers=make_authenticated_headers()
    )
    assert resp.status_code == 200
    event = resp.json()[0]
    assert event["timestamp_status"] == "unknown"
    assert event["timezone_status"] == "unknown"
