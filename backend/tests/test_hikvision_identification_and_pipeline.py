"""Synthetic-fixture unit tests for the Hikvision repair (no real evidence, no FFmpeg).

Pins the behaviours whose absence made the first Phase 26 delivery fail in the real
application (see test_hikvision_upload_workflow_real_evidence_integration.py for the
real-evidence, real-HTTP proof):

  - identification from the file's OWN Hikvision header (a bare UI upload, stored as
    `<evidence_id>_<name>`, has no sidecar and a prefixed filename);
  - a generic MP4 is never identified as Hikvision;
  - enumeration never clobbers what extraction established;
  - recording ids are evidence-scoped (no cross-case hijacking);
  - recovery for exported media is truthful (no CP Plus engine);
  - timestamp source classification and confirmed-device timezone handling.

Synthetic bytes are built from the header layout decoded (and cross-validated against
ffprobe) on the real evidence -- they are fixtures for logic, never presented as
Hikvision evidence.
"""

from __future__ import annotations

import struct
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.hikvision.models import (
    OBSERVED_HEADER_CODE_MEANINGS,
    HikvisionClipIdentificationStatus,
    HikvisionMediaHeader,
    lookup_known_hikvision_device,
)
from app.adapters.hikvision.parser import (
    CONFIDENCE_CONTAINER_HEADER,
    HikvisionParser,
    _header_probe_consistency,
    identify_exported_clip,
    parse_hikvision_export_filename,
    read_hikvision_media_header,
)
from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.core.recovery_manager import RecoveryManager
from app.core.timestamp_manager import TimestampManager
from app.media.media_probe import MediaProbeResult
from app.models import RecordingMetadata
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest

KNOWN_SERIAL = "0420220517CCWRJ98043179WCVU"

_BANNER = (
    "***************************************************************\n"
    "* Copyright Hikvision Digital Technology Co., Ltd.            *\n"
    "***************************************************************\n\n"
    "0 logs output\n\n\n"
    "User: admin Date:31/08/2026 Time: 18:54:26 made video export from device {serial}\n"
)


def hikvision_bytes(*, with_ps: bool = True, pad: int = 4532, tail: int = 4096) -> bytes:
    """The real header layout: `IMKH` + decoded 24-byte struct + zero padding + PS start code."""
    header = struct.pack("<4sHHHHHBBII", b"IMKH", 0x0102, 0, 2, 5, 0x7110, 1, 16, 8000, 8000)
    assert len(header) == 24
    return (
        header + b"\x00" * (pad - 24) + (b"\x00\x00\x01\xba" if with_ps else b"") + b"\x01" * tail
    )


def _write(directory: Path, name: str, data: bytes) -> Path:
    path = directory / name
    path.write_bytes(data)
    return path


def _identify(path: Path):
    with FileBackedReader(path) as reader:
        return identify_exported_clip(reader)


# --------------------------------------------------------------------------- header


def test_header_is_decoded_field_by_field(tmp_path: Path) -> None:
    path = _write(tmp_path, "x.bin", hikvision_bytes())
    with FileBackedReader(path) as reader:
        header = read_hikvision_media_header(reader)
    assert header == HikvisionMediaHeader(
        version=0x0102,
        device_id=0,
        system_format=2,
        video_format=5,
        audio_format=0x7110,
        audio_channels=1,
        audio_bits_per_sample=16,
        audio_sample_rate=8000,
        audio_bitrate_field=8000,
        ps_payload_offset=4532,
    )


@pytest.mark.parametrize(
    "data", [b"", b"IMK", b"\x00" * 64, b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64]
)
def test_non_hikvision_bytes_have_no_header_and_never_raise(tmp_path: Path, data: bytes) -> None:
    path = _write(tmp_path, "x.bin", data)
    with FileBackedReader(path) as reader:
        assert read_hikvision_media_header(reader) is None


def test_observed_code_table_only_lists_pairings_seen_on_real_evidence() -> None:
    """Guard against asserting codec meanings nobody validated."""
    assert OBSERVED_HEADER_CODE_MEANINGS == {
        "system_format": {0x0002: "mpeg"},
        "video_format": {0x0005: "hevc"},
        "audio_format": {0x7110: "pcm_mulaw"},
    }


# --------------------------------------------------------------------- identification


def test_bare_ui_upload_is_identified_from_its_own_header(tmp_path: Path) -> None:
    """The exact shape that failed: prefixed name, no sidecar anywhere."""
    path = _write(tmp_path, "EV-MTHBZZST_A01_20260829100000.mp4", hikvision_bytes())
    result = _identify(path)
    assert result.status == HikvisionClipIdentificationStatus.CONFIRMED_BY_CONTAINER_HEADER
    assert result.sidecar is None and result.known_device is None
    assert result.media_header is not None and result.media_header.ps_payload_offset == 4532
    assert "NOT determined" in result.reason  # never claims a model


def test_header_without_ps_payload_is_not_treated_as_identification(tmp_path: Path) -> None:
    path = _write(tmp_path, "clip.bin", hikvision_bytes(with_ps=False, tail=0))
    result = _identify(path)
    assert not result.status.is_confirmed
    assert any("no MPEG-PS pack start code" in w for w in result.warnings)


def test_generic_mp4_is_never_identified_as_hikvision(tmp_path: Path) -> None:
    """Task rule: never treat every MP4 as Hikvision."""
    path = _write(tmp_path, "holiday.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 4096)
    result = _identify(path)
    assert result.status == HikvisionClipIdentificationStatus.UNSUPPORTED
    with FileBackedReader(path) as reader:
        assert HikvisionParser(reader).enumerate_recordings().recordings == []


def test_hikvision_looking_filename_alone_is_not_confirmation(tmp_path: Path) -> None:
    path = _write(tmp_path, "A01_20260829100000.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 4096)
    result = _identify(path)
    assert result.status == HikvisionClipIdentificationStatus.FILENAME_PATTERN_ONLY
    assert not result.status.is_confirmed


# --------------------------------------------------------------------------- filename


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("A01_20260829100000.mp4", ("A01", 1, datetime(2026, 8, 29, 10, 0, 0))),
        ("EV-MTHBZZST_A01_20260829100000.mp4", ("A01", 1, datetime(2026, 8, 29, 10, 0, 0))),
        ("EV_1_A02_20260831080000.MP4", ("A02", 2, datetime(2026, 8, 31, 8, 0, 0))),
        ("D12_20260101235959.mp4", ("D12", 12, datetime(2026, 1, 1, 23, 59, 59))),
    ],
)
def test_filename_parse_tolerates_upload_prefix(name, expected) -> None:
    info = parse_hikvision_export_filename(name)
    assert info is not None
    assert (info.channel_label, info.channel_number, info.start_original) == expected


@pytest.mark.parametrize(
    "name",
    [
        "holiday.mp4",
        "A01_20261301100000.mp4",  # month 13
        "A01_20260829100000.avi",
        "A01_2026082910000.mp4",  # 13 digits
        "_20260829100000.mp4",
        "20260829100000.mp4",
    ],
)
def test_filename_parse_rejects_non_matching_names(name: str) -> None:
    assert parse_hikvision_export_filename(name) is None


# ---------------------------------------------------------------------------- sidecar


def _docx(path: Path, text: str) -> None:
    body = (
        '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.'
        'openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
        f"{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", body)


@pytest.mark.parametrize(
    "sidecar_name",
    [
        "EV-1_A01_20260829100000.txt",  # exact stored stem
        "A01_20260829100000.txt",  # original stem
        "EV-9_A01_20260829100000.txt",  # same sidecar uploaded as its own evidence (other prefix)
    ],
)
def test_sidecar_is_found_with_or_without_upload_prefix(tmp_path: Path, sidecar_name: str) -> None:
    clip = _write(tmp_path, "EV-1_A01_20260829100000.mp4", hikvision_bytes())
    _write(tmp_path, sidecar_name, _BANNER.format(serial=KNOWN_SERIAL).encode())
    result = _identify(clip)
    assert result.status == HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG
    assert result.sidecar is not None and result.sidecar.device_serial == KNOWN_SERIAL
    assert result.known_device is not None and result.known_device.model == "DS-7A04HQHI-K1"
    assert result.media_header is not None  # header corroboration is kept too


def test_docx_sidecar_is_read(tmp_path: Path) -> None:
    clip = _write(tmp_path, "A02_20260831080000.mp4", hikvision_bytes())
    _docx(
        tmp_path / "A02_20260831080000.docx",
        "Copyright Hikvision Digital Technology Co., Ltd. "
        f"User: admin Date:31/08/2026 Time: 19:07:38 made video export from device {KNOWN_SERIAL}",
    )
    result = _identify(clip)
    assert result.status == HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG
    assert result.sidecar is not None
    assert result.sidecar.export_timestamp == datetime(2026, 8, 31, 19, 7, 38)


def test_unrecognized_serial_is_confirmed_hikvision_but_claims_no_model(tmp_path: Path) -> None:
    clip = _write(tmp_path, "A01_20260829100000.mp4", hikvision_bytes())
    _write(tmp_path, "A01_20260829100000.txt", _BANNER.format(serial="SOMEOTHERSERIAL99").encode())
    result = _identify(clip)
    assert result.status == HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG
    assert result.sidecar is not None and result.sidecar.device_serial == "SOMEOTHERSERIAL99"
    assert result.known_device is None
    assert lookup_known_hikvision_device("SOMEOTHERSERIAL99") is None


def test_sidecar_without_banner_corroborates_nothing(tmp_path: Path) -> None:
    clip = _write(tmp_path, "A01_20260829100000.mp4", b"\x00" * 4096)
    _write(tmp_path, "A01_20260829100000.txt", b"just some unrelated text file")
    result = _identify(clip)
    assert result.status == HikvisionClipIdentificationStatus.FILENAME_PATTERN_ONLY
    assert any("does not carry the Hikvision copyright banner" in w for w in result.warnings)


# ------------------------------------------------------------------ probe consistency


def _probe(format_name="mpeg", vcodec="hevc", acodec="pcm_mulaw", channels=1, rate="8000"):
    streams = [{"codec_type": "video", "codec_name": vcodec}]
    if acodec:
        streams.append(
            {"codec_type": "audio", "codec_name": acodec, "channels": channels, "sample_rate": rate}
        )
    return MediaProbeResult(available=True, format_name=format_name, raw={"streams": streams})


_HEADER = HikvisionMediaHeader(0x0102, 0, 2, 5, 0x7110, 1, 16, 8000, 8000, 4532)


def test_header_agrees_with_probe() -> None:
    summary, contradiction = _header_probe_consistency(_HEADER, _probe())
    assert not contradiction
    assert summary.count("agrees with ffprobe") == 5


def test_header_contradicting_probe_is_reported() -> None:
    summary, contradiction = _header_probe_consistency(_HEADER, _probe(vcodec="h264"))
    assert contradiction and "header implies 'hevc' but ffprobe says 'h264'" in summary


def test_unknown_header_codes_are_not_cross_checked_or_guessed() -> None:
    header = HikvisionMediaHeader(0x0102, 0, 9, 9, 0x1234, 1, 16, 8000, 8000, 100)
    summary, contradiction = _header_probe_consistency(header, _probe())
    assert not contradiction and summary.count("not cross-checked") == 3


def test_header_only_enumeration_degrades_honestly_when_ffprobe_cannot_read(tmp_path: Path) -> None:
    """Synthetic bytes are not decodable media: nothing may be fabricated."""
    path = _write(tmp_path, "EV-5_A01_20260829100000.mp4", hikvision_bytes())
    with FileBackedReader(path) as reader:
        enumeration = HikvisionParser(reader, source_evidence_id="EV-5").enumerate_recordings()
    record = enumeration.recordings[0]
    assert record.recording_id == "HIKVISION-EXPORT-EV-5"
    assert record.confidence == CONFIDENCE_CONTAINER_HEADER
    assert (record.codec, record.fps, record.width, record.duration_ms) == (None, None, None, None)
    assert record.start_original == datetime(2026, 8, 29, 10, 0, 0) and record.end_original is None
    assert any("ffprobe" in w for w in record.warnings)


# ------------------------------------------------------------ manager-level (DB) tests


@pytest.fixture
def db_env(test_db, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    evidence_root = tmp_path / "evidence"
    artifact_root = tmp_path / "artifacts"
    evidence_root.mkdir()
    artifact_root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    yield test_db, evidence_root
    get_settings.cache_clear()


def _register(db, evidence_root: Path, case_pk: int, evidence_id: str, name: str, data: bytes):
    path = evidence_root / f"{evidence_id}_{name}"  # exactly how the upload route names it
    path.write_bytes(data)
    return EvidenceManager.register_evidence(
        db,
        case_pk,
        EvidenceCreateRequest(
            evidence_id=evidence_id, source_type="native_export", source_path=str(path)
        ),
    )


def _meta(db, recording_id: int) -> dict[str, str]:
    rows = db.query(RecordingMetadata).filter(RecordingMetadata.recording_id == recording_id).all()
    return {r.key: r.value for r in rows}


def test_header_only_upload_sets_vendor_but_never_model_serial_or_firmware(db_env) -> None:
    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-1", name="h"))
    ev = _register(db, root, case.id, "EV-A", "A01_20260829100000.mp4", hikvision_bytes())

    [recording] = RecordingManager.enumerate_recordings(db, ev.id)

    db.refresh(ev)
    assert ev.device.vendor == "Hikvision"
    assert ev.device.identification_method == "hikvision_container_header"
    assert ev.device.confidence == pytest.approx(CONFIDENCE_CONTAINER_HEADER)
    assert (ev.device.model, ev.device.firmware, ev.device.serial_number) == (None, None, None)
    assert ev.device.channel_count is None
    meta = _meta(db, recording.id)
    assert meta["vendor"] == "Hikvision"
    assert "hikvision_device_model" not in meta and "hikvision_device_serial" not in meta
    assert (recording.camera_id, recording.channel) == ("A01", 1)
    assert recording.start_original == datetime(2026, 8, 29, 10, 0, 0)


def test_sidecar_populates_device_row_for_the_confirmed_serial_only(db_env) -> None:
    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-2", name="h"))
    ev = _register(db, root, case.id, "EV-B", "A01_20260829100000.mp4", hikvision_bytes())
    (root / "A01_20260829100000.txt").write_text(_BANNER.format(serial=KNOWN_SERIAL))

    RecordingManager.enumerate_recordings(db, ev.id)

    db.refresh(ev)
    assert ev.device.identification_method == "hikvision_export_log_sidecar"
    assert ev.device.confidence == 1.0
    assert (ev.device.model, ev.device.firmware, ev.device.serial_number) == (
        "DS-7A04HQHI-K1",
        "V4.30.220, Build 220216",
        KNOWN_SERIAL,
    )
    assert ev.device.channel_count == 4


def test_unrecognized_serial_records_serial_but_no_model(db_env) -> None:
    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-3", name="h"))
    ev = _register(db, root, case.id, "EV-C", "A01_20260829100000.mp4", hikvision_bytes())
    (root / "A01_20260829100000.txt").write_text(_BANNER.format(serial="UNKNOWNSERIAL1"))

    RecordingManager.enumerate_recordings(db, ev.id)

    db.refresh(ev)
    assert ev.device.serial_number == "UNKNOWNSERIAL1"
    assert ev.device.model is None and ev.device.firmware is None
    assert ev.device.channel_count is None


def test_reenumeration_never_clobbers_extraction_owned_fields(db_env) -> None:
    """The `/recordings` route re-enumerates on every view; it must not overwrite what
    extraction wrote (container mp4 / measured fps) with the source's values."""
    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-4", name="h"))
    ev = _register(db, root, case.id, "EV-D", "A01_20260829100000.mp4", hikvision_bytes())
    [recording] = RecordingManager.enumerate_recordings(db, ev.id)

    # What `_extract_hikvision_recording` does after a successful remux + probe:
    recording.codec, recording.container = "hevc", "mp4"
    recording.width, recording.height, recording.fps = 1920, 1088, 15.0012
    recording.duration_ms, recording.artifact_id = 601237, "7"
    db.commit()

    [again] = RecordingManager.enumerate_recordings(db, ev.id)

    assert again.id == recording.id
    assert (again.codec, again.container, again.width, again.height) == ("hevc", "mp4", 1920, 1088)
    assert (again.fps, again.duration_ms, again.artifact_id) == (15.0012, 601237, "7")


def test_same_clip_in_two_cases_yields_two_independent_recordings(db_env) -> None:
    """`recording_id` is looked up globally; it must be evidence-scoped or the second
    case silently hijacks the first case's row."""
    db, root = db_env
    case_a = CaseManager.create_case(db, CaseCreateRequest(case_id="H-5A", name="a"))
    case_b = CaseManager.create_case(db, CaseCreateRequest(case_id="H-5B", name="b"))
    ev_a = _register(db, root, case_a.id, "EV-E1", "A01_20260829100000.mp4", hikvision_bytes())
    ev_b = _register(db, root, case_b.id, "EV-E2", "A01_20260829100000.mp4", hikvision_bytes())

    [rec_a] = RecordingManager.enumerate_recordings(db, ev_a.id)
    [rec_b] = RecordingManager.enumerate_recordings(db, ev_b.id)

    assert rec_a.id != rec_b.id
    assert (rec_a.evidence_id, rec_b.evidence_id) == (ev_a.id, ev_b.id)
    assert rec_a.recording_id != rec_b.recording_id


def test_recovery_for_exported_media_is_truthful_and_not_cp_plus(db_env) -> None:
    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-6", name="h"))
    ev = _register(db, root, case.id, "EV-F", "A01_20260829100000.mp4", hikvision_bytes())
    [recording] = RecordingManager.enumerate_recordings(db, ev.id)

    result = RecoveryManager.run_recovery(db, recording.id)

    assert result.status == "unsupported"
    assert result.artifact_id is None
    assert result.fragments_found is None and result.confidence is None
    assert result.frames_recovered is None
    assert "not_supported_for_exported_media" in result.notes
    for cp_plus_text in ("ADIT", "CPAV", "CPV_ANALYSIS_REPORT", "signature scanning"):
        assert cp_plus_text not in result.notes
    assert "carving: not_attempted" in result.notes
    assert "fragment_reconstruction: not_attempted" in result.notes
    db.refresh(recording)
    assert recording.recovery_status is None  # nothing was recovered


def test_timestamp_source_is_filename_derived_and_timezone_stays_unknown_without_a_device(
    db_env,
) -> None:
    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-7", name="h"))
    ev = _register(db, root, case.id, "EV-G", "A01_20260829100000.mp4", hikvision_bytes())
    [recording] = RecordingManager.enumerate_recordings(db, ev.id)

    outcome = TimestampManager.normalize_recording(db, recording.id)

    meta = _meta(db, recording.id)
    assert meta["timestamp_normalization_source"] == "filename_derived"
    assert meta["timestamp_normalization_status"] == "unknown"  # header-only: no tz knowable
    assert outcome.recording.start_normalized is None
    assert outcome.recording.start_original == datetime(2026, 8, 29, 10, 0, 0)  # untouched


def test_confirmed_device_timezone_is_applied_and_original_is_preserved(db_env) -> None:
    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-8", name="h"))
    ev = _register(db, root, case.id, "EV-H", "A01_20260829100000.mp4", hikvision_bytes())
    (root / "A01_20260829100000.txt").write_text(_BANNER.format(serial=KNOWN_SERIAL))
    [recording] = RecordingManager.enumerate_recordings(db, ev.id)

    outcome = TimestampManager.normalize_recording(db, recording.id)

    meta = _meta(db, recording.id)
    # Start: timezone-converted, no verified reference clock -> unverified. End: synthetic
    # bytes have no decodable duration, so end_original is None -> unknown. Combined: partial.
    assert meta["timestamp_normalization_status"] == "partial"
    assert meta["timestamp_normalization_method"] == "timezone_conversion"
    assert meta["timestamp_source_timezone"] == "Asia/Kolkata"
    assert "NTP is enabled" in meta["timestamp_source_timezone_basis"]
    # 10:00:00 at +05:30 == 04:30:00 UTC; the original stays as recorded.
    assert outcome.recording.start_normalized.replace(tzinfo=None) == datetime(
        2026, 8, 29, 4, 30, 0
    )
    assert outcome.recording.start_original == datetime(2026, 8, 29, 10, 0, 0)


def test_examiner_supplied_timezone_overrides_the_device_default(db_env) -> None:
    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-9", name="h"))
    ev = _register(db, root, case.id, "EV-I", "A01_20260829100000.mp4", hikvision_bytes())
    (root / "A01_20260829100000.txt").write_text(_BANNER.format(serial=KNOWN_SERIAL))
    [recording] = RecordingManager.enumerate_recordings(db, ev.id)

    outcome = TimestampManager.normalize_recording(
        db, recording.id, source_timezone="UTC", source_timezone_basis="examiner says UTC"
    )

    assert _meta(db, recording.id)["timestamp_source_timezone"] == "UTC"
    assert outcome.recording.start_normalized.replace(tzinfo=None) == datetime(
        2026, 8, 29, 10, 0, 0
    )


def test_reenumeration_never_clobbers_a_normalized_start(db_env) -> None:
    """Found in the real UI: 'Source Timezone Applied: Asia/Kolkata' but 'Normalized Start:
    unresolved' -- the `/recordings` route re-enumerates on every view and reset
    `start_normalized` to the enumerator's `None` placeholder."""
    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-10", name="h"))
    ev = _register(db, root, case.id, "EV-J", "A01_20260829100000.mp4", hikvision_bytes())
    (root / "A01_20260829100000.txt").write_text(_BANNER.format(serial=KNOWN_SERIAL))
    [recording] = RecordingManager.enumerate_recordings(db, ev.id)
    TimestampManager.normalize_recording(db, recording.id)
    db.refresh(recording)
    assert recording.start_normalized is not None  # precondition: normalization stored it

    stored = recording.start_normalized
    [again] = RecordingManager.enumerate_recordings(db, ev.id)

    assert again.start_normalized == stored
    assert again.start_normalized.replace(tzinfo=None) == datetime(2026, 8, 29, 4, 30, 0)


# ------------------------------------------------ export log uploaded as its own evidence


def test_export_log_uploaded_as_evidence_is_not_flagged_as_an_unsupported_recording(db_env) -> None:
    """The only in-UI way to give a bare clip its confirmed model is to upload the recorder's
    export log as a second evidence item in the same case. That log is a supporting document, not
    a recording -- it must not raise the MEDIUM "unsupported_format / No recordings enumerated"
    finding meant for a DVR export nobody could parse."""
    import json

    from app.core.processing_orchestrator import ProcessingOrchestrator
    from app.core.processing_policy import ProcessingPolicy
    from app.models import Finding, Job

    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-11", name="h"))
    _register(
        db,
        root,
        case.id,
        "EV-LOG",
        "A01_20260829100000.txt",
        _BANNER.format(serial=KNOWN_SERIAL).encode(),
    )

    ProcessingOrchestrator.process_case(db, case.id, policy=ProcessingPolicy(run_ai=False))

    flagged = (
        db.query(Finding)
        .filter(Finding.case_id == case.id, Finding.finding_type == "unsupported_format")
        .all()
    )
    assert flagged == []
    stage = db.query(Job).filter(Job.case_id == case.id, Job.job_type == "enumeration").one()
    assert stage.status == "skipped"
    assert "Hikvision device export log" in " ".join(json.loads(stage.warnings))


def test_an_unrecognized_text_file_registered_as_native_export_is_still_flagged(db_env) -> None:
    from app.core.processing_orchestrator import ProcessingOrchestrator
    from app.core.processing_policy import ProcessingPolicy
    from app.models import Finding

    db, root = db_env
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="H-12", name="h"))
    _register(db, root, case.id, "EV-TXT", "notes.txt", b"just some unrelated notes")

    ProcessingOrchestrator.process_case(db, case.id, policy=ProcessingPolicy(run_ai=False))

    flagged = (
        db.query(Finding)
        .filter(Finding.case_id == case.id, Finding.finding_type == "unsupported_format")
        .all()
    )
    assert len(flagged) == 1


def test_is_hikvision_export_log_recognizes_only_real_logs(tmp_path: Path) -> None:
    from app.adapters.hikvision.parser import is_hikvision_export_log

    good = _write(tmp_path, "a.txt", _BANNER.format(serial=KNOWN_SERIAL).encode())
    other_txt = _write(tmp_path, "b.txt", b"nothing to see")
    binary = _write(tmp_path, "c.txt", bytes(range(256)) * 8)
    wrong_ext = _write(tmp_path, "d.bin", _BANNER.format(serial=KNOWN_SERIAL).encode())
    huge = _write(
        tmp_path, "e.txt", b"x" * (2 * 1024 * 1024) + _BANNER.format(serial=KNOWN_SERIAL).encode()
    )
    docx = tmp_path / "f.docx"
    _docx(docx, "Copyright Hikvision Digital Technology Co., Ltd. 0 logs output")

    assert is_hikvision_export_log(good)
    assert is_hikvision_export_log(docx)
    assert not any(is_hikvision_export_log(p) for p in (other_txt, binary, wrong_ext, huge))
    assert not is_hikvision_export_log(tmp_path / "missing.txt")
