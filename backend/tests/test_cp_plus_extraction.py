"""Tests for CP Plus HEVC elementary-stream reconstruction
(app/adapters/cp_plus/extraction.py), Phase 9.

Isolated logic cases use small, hand-built synthetic byte buffers, matching
test_cp_plus_container.py's own convention: constructed only from the
already-evidence-validated constants and framing (magic/length/footer), a
realistic 33-byte record-prefix before the Annex-B start code (matching the
real evidence's `[4-byte timestamp][29 unknown bytes][NAL data]` layout,
re-verified against the real evidence during Phase 9 implementation — see
this module's own docstring), never used to invent a new CP Plus structure.
The real-evidence acceptance test lives in
test_cp_plus_extraction_real_evidence_integration.py.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.cp_plus.extraction import extract_hevc_elementary_stream
from app.adapters.cp_plus.models import (
    ADIT_MAGIC,
    OUTER_HEADER_SIZE,
    RECORD_FOOTER_MAGIC,
    RECORD_HEADER_SIZE,
    RECORD_MAGIC,
)

_ANNEXB_PREFIX = b"\x00" * 33  # record-timestamp + unknown per-record header bytes


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


def _nal(nal_unit_type: int, payload: bytes = b"\xff\xee") -> bytes:
    """One Annex-B NAL: 3-byte start code + a 1-byte HEVC NAL header + payload."""
    first_byte = (nal_unit_type << 1) & 0xFF
    return b"\x00\x00\x01" + bytes([first_byte, 0x01]) + payload


def _keyframe_marker_body() -> bytes:
    # VPS(32) + SPS(33) + PPS(34) + IDR(19), concatenated Annex-B, matching
    # the real evidence's file-opening record layout.
    return _ANNEXB_PREFIX + _nal(32) + _nal(33) + _nal(34) + _nal(19, b"\xaa\xbb\xcc")


def _video_frame_body(payload: bytes = b"\x11\x22\x33") -> bytes:
    return _ANNEXB_PREFIX + _nal(1, payload)  # TRAIL_R, an ordinary slice


def _write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_extracts_keyframe_and_frame_records_in_order(tmp_path: Path):
    content = (
        _outer_header_bytes()
        + _record_bytes(0xFD, 1, _keyframe_marker_body())
        + _record_bytes(0xFC, 2, _video_frame_body())
    )
    path = _write(tmp_path, "two_records.bin", content)
    output = io.BytesIO()
    with FileBackedReader(path) as reader:
        result = extract_hevc_elementary_stream(reader, output, segment_label="seg-1")

    assert result.frames_written == 2
    assert result.keyframes_written == 1
    assert result.frames_missing_nal == 0
    assert result.truncated is False
    assert result.corrupted is False

    written = output.getvalue()
    # Keyframe record's 4 concatenated NALs, then the frame record's 1 NAL.
    expected = (
        _nal(32) + _nal(33) + _nal(34) + _nal(19, b"\xaa\xbb\xcc") + _nal(1, b"\x11\x22\x33")
    )
    assert written == expected
    assert result.bytes_written == len(expected)


def test_video_fixed_auxiliary_and_telemetry_records_contribute_nothing(tmp_path: Path):
    content = (
        _outer_header_bytes()
        + _record_bytes(0xFC, 1, _video_frame_body())
        + _record_bytes(0xF0, 2, b"\x00" * 344)  # opaque, no start code
        + _record_bytes(0xF1, 3, b'{"ok": true}')
    )
    path = _write(tmp_path, "aux_and_telemetry.bin", content)
    output = io.BytesIO()
    with FileBackedReader(path) as reader:
        result = extract_hevc_elementary_stream(reader, output, segment_label="seg-1")

    assert result.frames_written == 1
    assert result.skipped_video_fixed_auxiliary == 1
    assert result.skipped_telemetry == 1
    assert result.skipped_unrecognized == 0
    assert output.getvalue() == _nal(1, b"\x11\x22\x33")


def test_frame_record_with_no_nal_start_code_is_warned_and_omitted(tmp_path: Path):
    content = _outer_header_bytes() + _record_bytes(0xFC, 1, b"\x00" * 40)  # no start code
    path = _write(tmp_path, "no_nal.bin", content)
    output = io.BytesIO()
    with FileBackedReader(path) as reader:
        result = extract_hevc_elementary_stream(reader, output, segment_label="seg-1")

    assert result.frames_written == 0
    assert result.frames_missing_nal == 1
    assert output.getvalue() == b""
    assert any("no Annex-B NAL start code" in w for w in result.warnings)


def test_truncated_trailing_record_is_reported_not_raised(tmp_path: Path):
    good = _record_bytes(0xFC, 1, _video_frame_body())
    # A second record header claiming a body far larger than what actually follows.
    bad_header = RECORD_MAGIC + struct.pack("<III", 0xFC, 2, 999_999)
    content = _outer_header_bytes() + good + bad_header
    path = _write(tmp_path, "truncated.bin", content)
    output = io.BytesIO()
    with FileBackedReader(path) as reader:
        result = extract_hevc_elementary_stream(reader, output, segment_label="seg-1")

    assert result.frames_written == 1
    assert result.truncated is True
    assert result.corrupted is False
    assert result.warnings


def test_trailing_ff_padding_is_not_flagged_as_truncated_or_corrupted(tmp_path: Path):
    content = (
        _outer_header_bytes()
        + _record_bytes(0xFC, 1, _video_frame_body())
        + b"\xff\xff\xff\xff" * 4
    )
    path = _write(tmp_path, "padded.bin", content)
    output = io.BytesIO()
    with FileBackedReader(path) as reader:
        result = extract_hevc_elementary_stream(reader, output, segment_label="seg-1")

    assert result.frames_written == 1
    assert result.truncated is False
    assert result.corrupted is False


def test_bad_magic_mid_stream_is_flagged_corrupted(tmp_path: Path):
    content = (
        _outer_header_bytes() + _record_bytes(0xFC, 1, _video_frame_body()) + b"XXXXXXXXXXXXXXXX"
    )
    path = _write(tmp_path, "corrupt.bin", content)
    output = io.BytesIO()
    with FileBackedReader(path) as reader:
        result = extract_hevc_elementary_stream(reader, output, segment_label="seg-1")

    assert result.frames_written == 1
    assert result.corrupted is True
    assert result.truncated is False
