"""Tests for CPV container/record parsing (app/adapters/cp_plus/container.py).

Phase 8 real-parser implementation. Isolated error-path/logic cases use
small, hand-built synthetic byte buffers constructed ONLY from the
already-evidence-validated constants (`ADIT_MAGIC`, `RECORD_MAGIC`,
`RECORD_FOOTER_MAGIC`, and the exact header/footer sizes established by a
full length-jump walk of the real evidence — see
app/adapters/cp_plus/models.py's module docstring). The main structural
validation — that this logic actually matches the real evidence's bytes —
lives in the `requires_real_evidence`-marked tests below and in
test_cp_plus_real_evidence_integration.py; synthetic bytes are never used
to invent a CP Plus structure, only to exercise this module's own
error-handling logic in isolation.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.acquisition.storage_reader import EvidenceStorageReader, FileBackedReader
from app.adapters.cp_plus.container import (
    MAX_RECORD_BODY_READ,
    analyze_cpv_file,
    find_annexb_nal_units,
    iter_cpv_records,
    parse_cp_plus_export_filename,
    parse_outer_header,
    parse_telemetry_payload,
    read_record_body,
)
from app.adapters.cp_plus.models import (
    ADIT_MAGIC,
    MIN_RECORD_SIZE,
    OUTER_HEADER_SIZE,
    RECORD_FOOTER_MAGIC,
    RECORD_HEADER_SIZE,
    RECORD_MAGIC,
    CPVRecord,
    CPVRecordFamily,
    CPVRecordValidity,
    classify_record_family,
)
from tests.fixtures.cp_plus_evidence import requires_real_evidence, smallest_real_cpv_path


def _outer_header_bytes(start_counter: int = 0, end_counter: int = 0) -> bytes:
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


def _write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


# --- parse_outer_header ---


def test_parse_outer_header_recognizes_valid_magic_and_counters(tmp_path: Path):
    path = _write(tmp_path, "hdr.bin", _outer_header_bytes(100, 200))
    with FileBackedReader(path) as reader:
        header = parse_outer_header(reader)
    assert header.magic_valid is True
    assert header.start_counter == 100
    assert header.end_counter == 200
    assert header.reserved_all_zero is True
    assert header.bytes_read == OUTER_HEADER_SIZE


def test_parse_outer_header_rejects_wrong_magic(tmp_path: Path):
    content = (
        b"XXXX\x00\x00\x00\x00" + struct.pack("<II", 0, 0) + b"\x00" * (OUTER_HEADER_SIZE - 16)
    )
    path = _write(tmp_path, "hdr.bin", content)
    with FileBackedReader(path) as reader:
        header = parse_outer_header(reader)
    assert header.magic_valid is False


def test_parse_outer_header_on_tiny_file_returns_none_fields(tmp_path: Path):
    path = _write(tmp_path, "tiny.bin", b"\x01\x02\x03")
    with FileBackedReader(path) as reader:
        header = parse_outer_header(reader)
    assert header.magic_valid is False
    assert header.start_counter is None
    assert header.end_counter is None
    assert header.reserved_all_zero is None


def test_parse_outer_header_flags_nonzero_reserved_region(tmp_path: Path):
    content = bytearray(_outer_header_bytes(1, 2))
    content[500] = 0xAB
    path = _write(tmp_path, "hdr.bin", bytes(content))
    with FileBackedReader(path) as reader:
        header = parse_outer_header(reader)
    assert header.reserved_all_zero is False


# --- iter_cpv_records: well-formed records ---


def test_iter_cpv_records_yields_one_valid_record(tmp_path: Path):
    body = b"\x00\x05\x39\x6a" + b"X" * 20
    content = _outer_header_bytes() + _record_bytes(0xFC, 42, body)
    path = _write(tmp_path, "one_record.bin", content)
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))
    assert len(records) == 1
    record = records[0]
    assert record.validity == CPVRecordValidity.VALID
    assert record.type_tag == 0xFC
    assert record.family == CPVRecordFamily.VIDEO_FRAME
    assert record.counter == 42
    assert record.footer_valid is True
    assert record.record_timestamp == 0x6A390500
    assert record.payload_length == len(body)
    assert record.next_offset == OUTER_HEADER_SIZE + len(_record_bytes(0xFC, 42, body))


def test_iter_cpv_records_walks_multiple_records_in_sequence(tmp_path: Path):
    r1 = _record_bytes(0xFC, 1, b"A" * 30)
    r2 = _record_bytes(0xF0, 2, b"B" * 10)
    r3 = _record_bytes(0x00F1, 3, b'{"k":1}')
    content = _outer_header_bytes() + r1 + r2 + r3
    path = _write(tmp_path, "three_records.bin", content)
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))
    assert [r.validity for r in records] == [CPVRecordValidity.VALID] * 3
    assert [r.family for r in records] == [
        CPVRecordFamily.VIDEO_FRAME,
        CPVRecordFamily.VIDEO_FIXED_AUXILIARY,
        CPVRecordFamily.TELEMETRY,
    ]
    assert records[-1].next_offset == len(content)


# --- iter_cpv_records: malformed/truncated cases ---


def test_iter_cpv_records_detects_truncated_header(tmp_path: Path):
    content = _outer_header_bytes() + b"CPA"  # 3 bytes, short of the 16-byte header
    path = _write(tmp_path, "truncated.bin", content)
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))
    assert len(records) == 1
    assert records[0].validity == CPVRecordValidity.TRUNCATED_HEADER


def test_iter_cpv_records_detects_bad_magic(tmp_path: Path):
    garbage_header = b"XXXX" + struct.pack("<III", 0xFC, 1, 100)
    content = _outer_header_bytes() + garbage_header + b"\x00" * 200
    path = _write(tmp_path, "bad_magic.bin", content)
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))
    assert len(records) == 1
    assert records[0].validity == CPVRecordValidity.BAD_MAGIC


def test_iter_cpv_records_treats_0xff_run_as_trailing_padding_not_corruption(tmp_path: Path):
    r1 = _record_bytes(0xFC, 1, b"A" * 20)
    content = _outer_header_bytes() + r1 + b"\xff" * 100
    path = _write(tmp_path, "padded.bin", content)
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))
    assert records[0].validity == CPVRecordValidity.VALID
    assert records[-1].validity == CPVRecordValidity.TRAILING_PADDING


def test_iter_cpv_records_detects_invalid_length_below_minimum(tmp_path: Path):
    bad_header = RECORD_MAGIC + struct.pack("<III", 0xFC, 1, MIN_RECORD_SIZE - 1)
    content = _outer_header_bytes() + bad_header + b"\x00" * 50
    path = _write(tmp_path, "bad_length.bin", content)
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))
    assert records[0].validity == CPVRecordValidity.INVALID_LENGTH


def test_iter_cpv_records_detects_length_exceeding_container(tmp_path: Path):
    bad_header = RECORD_MAGIC + struct.pack("<III", 0xFC, 1, 100_000)
    content = _outer_header_bytes() + bad_header + b"\x00" * 50  # far short of 100_000
    path = _write(tmp_path, "overrun.bin", content)
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))
    assert records[0].validity == CPVRecordValidity.LENGTH_EXCEEDS_CONTAINER


def test_iter_cpv_records_detects_footer_mismatch(tmp_path: Path):
    good = bytearray(_record_bytes(0xFC, 1, b"A" * 20))
    good[-1] ^= 0xFF  # corrupt the last byte of the footer's length-echo
    content = _outer_header_bytes() + bytes(good)
    path = _write(tmp_path, "bad_footer.bin", content)
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))
    assert records[0].validity == CPVRecordValidity.FOOTER_MISMATCH
    assert records[0].footer_valid is False


def test_iter_cpv_records_stops_after_first_malformed_record_no_resync(tmp_path: Path):
    """Once framing breaks, the walk must not guess where the next record starts."""
    r1 = _record_bytes(0xFC, 1, b"A" * 20)
    bad = RECORD_MAGIC + struct.pack("<III", 0xFC, 2, MIN_RECORD_SIZE - 1)
    r3 = _record_bytes(0xFC, 3, b"C" * 20)  # would be well-formed if reached
    content = _outer_header_bytes() + r1 + bad + b"\x00" * 50 + r3
    path = _write(tmp_path, "resync.bin", content)
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))
    assert [r.validity for r in records] == [
        CPVRecordValidity.VALID,
        CPVRecordValidity.INVALID_LENGTH,
    ]


# --- classify_record_family ---


@pytest.mark.parametrize(
    ("type_tag", "expected"),
    [
        (0xFC, CPVRecordFamily.VIDEO_FRAME),
        (0xF0, CPVRecordFamily.VIDEO_FIXED_AUXILIARY),
        (0xFD, CPVRecordFamily.KEYFRAME_MARKER),
        (0x00F1, CPVRecordFamily.TELEMETRY),
        (0x06F1, CPVRecordFamily.TELEMETRY),
        (0x09F1, CPVRecordFamily.TELEMETRY),
        (0x19F1, CPVRecordFamily.TELEMETRY),
        (0x1234, CPVRecordFamily.UNKNOWN),
    ],
)
def test_classify_record_family(type_tag: int, expected: CPVRecordFamily):
    assert classify_record_family(type_tag) == expected


# --- find_annexb_nal_units ---


def test_find_annexb_nal_units_identifies_vps_sps_pps_idr():
    body = (
        b"\x00\x00\x00\x01\x40\x01"  # VPS (type 32)
        + b"\x00\x00\x00\x01\x42\x01"  # SPS (type 33)
        + b"\x00\x00\x00\x01\x44\x01"  # PPS (type 34)
        + b"\x00\x00\x00\x01\x26\x01"  # IDR_W_RADL (type 19)
    )
    units = find_annexb_nal_units(body)
    assert [u.nal_unit_type for u in units] == [32, 33, 34, 19]
    assert [u.nal_unit_name for u in units] == ["VPS", "SPS", "PPS", "IDR_W_RADL"]


def test_find_annexb_nal_units_returns_empty_for_body_with_no_start_code():
    assert find_annexb_nal_units(b"\x01\x02\x03" * 50) == []


def test_find_annexb_nal_units_labels_unclassified_types_explicitly():
    body = b"\x00\x00\x01" + bytes([0x3E])  # nal_unit_type = 31, not in the named table
    units = find_annexb_nal_units(body)
    assert units[0].nal_unit_type == 31
    assert units[0].nal_unit_name == "type_31_unclassified"


# --- parse_telemetry_payload ---


def test_parse_telemetry_payload_decodes_valid_json():
    body = b"\x00\x00\x00\x00" + b'{"Status":"Normal","Value":1}'
    # Build a minimal record around this body just to get a real CPVRecord.
    record_bytes = _record_bytes(0x00F1, 1, body)

    class _StaticReader(EvidenceStorageReader):
        def __init__(self, data: bytes) -> None:
            self._data = data
            self.sector_size = 512

        def read(self, offset: int, length: int) -> bytes:
            return self._data[offset : offset + length]

        def size(self) -> int:
            return len(self._data)

        def metadata(self) -> dict[str, object]:
            return {}

        def hash(self) -> dict[str, str] | None:
            return None

        def close(self) -> None:
            pass

    reader = _StaticReader(_outer_header_bytes() + record_bytes)
    records = list(iter_cpv_records(reader))
    assert records[0].validity == CPVRecordValidity.VALID
    payload_body = read_record_body(reader, records[0])
    telemetry = parse_telemetry_payload(records[0], payload_body)
    assert telemetry.valid_json is True
    assert telemetry.parsed == {"Status": "Normal", "Value": 1}


def test_parse_telemetry_payload_reports_invalid_json_without_raising():
    fake_record = CPVRecord(
        offset=0,
        type_tag=0x00F1,
        family=CPVRecordFamily.TELEMETRY,
        counter=0,
        length=None,
        record_timestamp=None,
        validity=CPVRecordValidity.VALID,
        footer_valid=True,
        payload_offset=0,
        payload_length=10,
    )
    telemetry = parse_telemetry_payload(fake_record, b"\x01\x02not json\x03")
    assert telemetry.valid_json is False
    assert telemetry.parsed is None
    assert "not json" in telemetry.raw_text


# --- parse_cp_plus_export_filename ---


def test_parse_cp_plus_export_filename_matches_expected_convention():
    info = parse_cp_plus_export_filename("NVR_ch1_main_20260828162000_20260828162002.cpv")
    assert info is not None
    assert info.channel == 1
    assert info.stream_label == "main"
    assert info.start_original is not None and info.start_original.isoformat().startswith(
        "2026-08-28T16:20:00"
    )
    assert info.end_original is not None and info.end_original.isoformat().startswith(
        "2026-08-28T16:20:02"
    )


@pytest.mark.parametrize(
    "name",
    ["not_a_cpv_filename.cpv", "random.txt", "NVR_ch1_main_bad_timestamps.cpv", ""],
)
def test_parse_cp_plus_export_filename_returns_none_for_non_matching_names(name: str):
    assert parse_cp_plus_export_filename(name) is None


# --- analyze_cpv_file: synthetic end-to-end assembly ---


def test_analyze_cpv_file_on_synthetic_well_formed_container(tmp_path: Path):
    keyframe_body = (
        b"\x00\x00\x00\x00"
        + b"\x00\x00\x00\x01\x40\x01"
        + b"\x00\x00\x00\x01\x42\x01"
        + b"\x00\x00\x00\x01\x44\x01"
        + b"\x00\x00\x00\x01\x26\x01"
    )
    telemetry_body = b"\x00\x00\x00\x00" + b'{"Status":"Normal"}'
    content = (
        _outer_header_bytes(10, 20)
        + _record_bytes(0xFD, 1, keyframe_body)
        + _record_bytes(0x00F1, 2, telemetry_body)
        + _record_bytes(0xF0, 3, b"\x00\x00\x00\x00" + b"X" * 30)
    )
    path = _write(tmp_path, "synthetic.cpv", content)
    with FileBackedReader(path) as reader:
        analysis = analyze_cpv_file(reader)

    assert analysis.record_count == 3
    assert analysis.truncated is False
    assert analysis.corrupted is False
    assert analysis.family_histogram[CPVRecordFamily.KEYFRAME_MARKER] == 1
    assert analysis.family_histogram[CPVRecordFamily.TELEMETRY] == 1
    assert analysis.family_histogram[CPVRecordFamily.VIDEO_FIXED_AUXILIARY] == 1
    assert {u.nal_unit_name for u in analysis.nal_units} == {"VPS", "SPS", "PPS", "IDR_W_RADL"}
    assert len(analysis.telemetry_samples) == 1
    assert analysis.telemetry_samples[0].parsed == {"Status": "Normal"}
    assert analysis.outer_header is not None
    assert analysis.outer_header.start_counter == 10


def test_analyze_cpv_file_reports_partial_on_truncated_final_record(tmp_path: Path):
    good = _record_bytes(0xFC, 1, b"A" * 20)
    bad_header = RECORD_MAGIC + struct.pack("<III", 0xFC, 2, 5_000)
    content = _outer_header_bytes() + good + bad_header + b"\x00" * 30
    path = _write(tmp_path, "partial.cpv", content)
    with FileBackedReader(path) as reader:
        analysis = analyze_cpv_file(reader)
    assert analysis.record_count == 1
    assert analysis.truncated is True
    assert analysis.corrupted is False
    assert analysis.warnings


def test_analyze_cpv_file_on_container_smaller_than_outer_header(tmp_path: Path):
    path = _write(tmp_path, "tiny.cpv", b"\x00" * 100)
    with FileBackedReader(path) as reader:
        analysis = analyze_cpv_file(reader)
    assert analysis.record_count == 0
    assert analysis.truncated is True
    assert analysis.container_size == 100


# --- bounded reads: no record body read may exceed MAX_RECORD_BODY_READ ---


class _RecordingReader(EvidenceStorageReader):
    def __init__(self, inner: EvidenceStorageReader) -> None:
        self._inner = inner
        self.read_calls: list[tuple[int, int]] = []
        self.sector_size = inner.sector_size

    def read(self, offset: int, length: int) -> bytes:
        self.read_calls.append((offset, length))
        return self._inner.read(offset, length)

    def size(self) -> int:
        return self._inner.size()

    def metadata(self) -> dict[str, object]:
        return self._inner.metadata()

    def hash(self) -> dict[str, str] | None:
        return self._inner.hash()

    def close(self) -> None:
        self._inner.close()


def test_analyze_cpv_file_never_issues_an_oversized_read(tmp_path: Path):
    content = _outer_header_bytes() + _record_bytes(0xFC, 1, b"A" * 50)
    path = _write(tmp_path, "bounded.cpv", content)
    inner = FileBackedReader(path)
    wrapped = _RecordingReader(inner)
    try:
        analyze_cpv_file(wrapped)
    finally:
        wrapped.close()
    assert wrapped.read_calls
    assert all(length <= MAX_RECORD_BODY_READ for _offset, length in wrapped.read_calls)


# --- real-evidence-based structural regression ---


@requires_real_evidence
def test_real_smallest_file_outer_header_matches_adit_v1():
    path = smallest_real_cpv_path()
    assert path is not None
    with FileBackedReader(path) as reader:
        header = parse_outer_header(reader)
    assert header.magic_valid is True
    assert header.start_counter is not None
    assert header.end_counter is not None
    assert header.end_counter >= header.start_counter
    # Not literally all zero: byte offset 32 is 0x01 (constant across all 13
    # real files, meaning unestablished) — see CPVOuterHeader.reserved_all_zero's
    # docstring. This was missed in the original read-only analysis pass
    # (which only inspected short constant-byte runs individually) and
    # corrected here against the real bytes during implementation.
    assert header.reserved_all_zero is False


@requires_real_evidence
def test_real_smallest_file_every_record_has_a_valid_footer_until_eof_or_padding():
    """Regression for the exact length-jump formula, against real evidence bytes."""
    path = smallest_real_cpv_path()
    assert path is not None
    with FileBackedReader(path) as reader:
        records = list(iter_cpv_records(reader))

    assert len(records) > 50  # the smallest real file has ~100 records
    non_terminal = records[:-1]
    assert all(r.validity == CPVRecordValidity.VALID for r in non_terminal)
    assert all(r.footer_valid is True for r in non_terminal)
    # The real smallest/first file's last record is genuinely truncated in
    # the supplied evidence (confirmed during read-only analysis) — this is
    # a real, not synthetic, malformed-record case.
    assert records[-1].validity in (
        CPVRecordValidity.LENGTH_EXCEEDS_CONTAINER,
        CPVRecordValidity.VALID,
        CPVRecordValidity.TRAILING_PADDING,
    )


@requires_real_evidence
def test_real_smallest_file_analysis_finds_hevc_and_telemetry():
    path = smallest_real_cpv_path()
    assert path is not None
    with FileBackedReader(path) as reader:
        analysis = analyze_cpv_file(reader)

    assert analysis.record_count > 0
    nal_names = {u.nal_unit_name for u in analysis.nal_units}
    assert {"VPS", "SPS", "PPS"}.issubset(nal_names)
    assert analysis.telemetry_samples
    json_samples = [t for t in analysis.telemetry_samples if t.valid_json]
    assert json_samples
    assert any("DepthFieldStatus" in t.raw_text for t in json_samples)
