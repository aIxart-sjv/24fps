"""Tests for CP Plus vendor-specific recovery (app/adapters/cp_plus/recovery.py
and its wiring into CPPlusAdapter), Phase 10.

Synthetic fixtures, matching test_cp_plus_extraction.py's own convention:
hand-built byte buffers using only the already-evidence-validated framing
constants and a realistic 33-byte record prefix. The real-evidence
acceptance test lives in
test_cp_plus_recovery_real_evidence_integration.py.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.cp_plus import CPPlusAdapter
from app.adapters.cp_plus.models import (
    ADIT_MAGIC,
    OUTER_HEADER_SIZE,
    RECORD_FOOTER_MAGIC,
    RECORD_HEADER_SIZE,
    RECORD_MAGIC,
    CPVSegmentDescriptor,
)
from app.adapters.cp_plus.recovery import (
    DELETED_RECOVERY_NOT_VALIDATED_STATEMENT,
    find_deleted_cpv_recordings,
    reconstruct_cpv_fragments,
    recover_damaged_cpv_segment,
)
from app.recovery import RecoveryStatus

_ANNEXB_PREFIX = b"\x00" * 33


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
    first_byte = (nal_unit_type << 1) & 0xFF
    return b"\x00\x00\x01" + bytes([first_byte, 0x01]) + payload


def _keyframe_marker_body() -> bytes:
    return _ANNEXB_PREFIX + _nal(32) + _nal(33) + _nal(34) + _nal(19, b"\xaa\xbb\xcc")


def _video_frame_body(payload: bytes = b"\x11\x22\x33") -> bytes:
    return _ANNEXB_PREFIX + _nal(1, payload)


def _write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


# --- find_deleted_cpv_recordings (RECOVERY FRAMEWORK / UNVALIDATED PATH) ---


def test_find_deleted_recordings_always_reports_unsupported(tmp_path: Path):
    result = find_deleted_cpv_recordings()
    assert result.status == RecoveryStatus.UNSUPPORTED
    assert DELETED_RECOVERY_NOT_VALIDATED_STATEMENT in result.reason


def test_adapter_find_deleted_recordings_matches_module_function(tmp_path: Path):
    content = _outer_header_bytes(1, 2) + _record_bytes(0xFD, 1, _keyframe_marker_body())
    path = _write(tmp_path, "seg.bin", content)
    with FileBackedReader(path) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id="SEG-1")
        result = adapter.find_deleted_recordings()
    assert result.metadata["recovery_status"] == RecoveryStatus.UNSUPPORTED.value
    assert DELETED_RECOVERY_NOT_VALIDATED_STATEMENT in result.warnings[0]


# --- recover_damaged_cpv_segment / CPPlusAdapter.recover_recording ---


def test_recover_recording_on_clean_segment_reports_recovered(tmp_path: Path):
    content = (
        _outer_header_bytes(100, 103)
        + _record_bytes(0xFD, 100, _keyframe_marker_body())
        + _record_bytes(0xFC, 101, _video_frame_body())
        + _record_bytes(0xFC, 102, _video_frame_body())
    )
    path = _write(tmp_path, "clean.bin", content)
    with FileBackedReader(path) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id="SEG-1")
        enumeration = adapter.enumerate_recordings()
        recording_id = enumeration.recordings[0]
        output = io.BytesIO()
        result = adapter.recover_recording(recording_id, destination=output)

    assert result.metadata["recovery_status"] == RecoveryStatus.RECOVERED.value
    assert int(result.metadata["frames_recovered"]) == 3
    assert result.metadata["frame_continuity"] == "1.0"
    assert result.confidence == 1.0
    assert len(output.getvalue()) > 0


def test_recover_recording_on_truncated_segment_reports_partial(tmp_path: Path):
    good = _record_bytes(0xFD, 100, _keyframe_marker_body()) + _record_bytes(
        0xFC, 101, _video_frame_body()
    )
    bad_header = RECORD_MAGIC + struct.pack("<III", 0xFC, 102, 999_999)
    content = _outer_header_bytes(100, 103) + good + bad_header
    path = _write(tmp_path, "truncated.bin", content)
    with FileBackedReader(path) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id="SEG-1")
        enumeration = adapter.enumerate_recordings()
        recording_id = enumeration.recordings[0]
        output = io.BytesIO()
        result = adapter.recover_recording(recording_id, destination=output)

    assert result.metadata["recovery_status"] == RecoveryStatus.PARTIAL.value
    assert int(result.metadata["bytes_recovered"]) > 0
    assert result.warnings


def test_recover_recording_with_no_video_records_reports_no_recovery_found(tmp_path: Path):
    content = _outer_header_bytes(1, 2) + _record_bytes(0xF1, 1, b'{"telemetry": true}')
    path = _write(tmp_path, "no_video.bin", content)
    with FileBackedReader(path) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id="SEG-1")
        enumeration = adapter.enumerate_recordings()
        recording_id = enumeration.recordings[0]
        output = io.BytesIO()
        result = adapter.recover_recording(recording_id, destination=output)

    assert result.metadata["recovery_status"] == RecoveryStatus.NO_RECOVERY_FOUND.value
    assert output.getvalue() == b""


def test_recover_recording_rejects_unknown_recording_id(tmp_path: Path):
    content = _outer_header_bytes(1, 2) + _record_bytes(0xFD, 1, _keyframe_marker_body())
    path = _write(tmp_path, "seg.bin", content)
    with FileBackedReader(path) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id="SEG-1")
        result = adapter.recover_recording("does-not-exist")
    assert result.metadata["recovery_status"] == RecoveryStatus.FAILED.value


def test_recover_damaged_cpv_segment_never_raises_on_garbage(tmp_path: Path):
    path = _write(tmp_path, "garbage.bin", b"not a cpv file at all" * 100)
    output = io.BytesIO()
    with FileBackedReader(path) as reader:
        result = recover_damaged_cpv_segment(reader, output, segment_label="garbage")
    assert result.status == RecoveryStatus.NO_RECOVERY_FOUND
    assert result.bytes_recovered == 0


# --- reconstruct_fragments ---


def test_adapter_reconstruct_fragments_reports_unsupported_for_single_bound_segment(
    tmp_path: Path,
):
    content = _outer_header_bytes(1, 2) + _record_bytes(0xFD, 1, _keyframe_marker_body())
    path = _write(tmp_path, "seg.bin", content)
    with FileBackedReader(path) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id="SEG-1")
        result = adapter.reconstruct_fragments("some-recording-id")
    assert result.metadata["recovery_status"] == RecoveryStatus.UNSUPPORTED.value
    assert "single segment" in result.warnings[0]


def test_reconstruct_cpv_fragments_reorders_shuffled_descriptors():
    descriptors = [
        CPVSegmentDescriptor(label="seg3", start_counter=200, end_counter=300, readable=True),
        CPVSegmentDescriptor(label="seg1", start_counter=0, end_counter=100, readable=True),
        CPVSegmentDescriptor(label="seg2", start_counter=100, end_counter=200, readable=True),
    ]
    link_result = reconstruct_cpv_fragments(descriptors)
    assert [s.label for s in link_result.segments] == ["seg1", "seg2", "seg3"]
    assert link_result.overall_status.value == "continuous"


def test_reconstruct_cpv_fragments_detects_a_missing_segment():
    descriptors = [
        CPVSegmentDescriptor(label="seg1", start_counter=0, end_counter=100, readable=True),
        CPVSegmentDescriptor(label="seg3", start_counter=200, end_counter=300, readable=True),
    ]
    link_result = reconstruct_cpv_fragments(descriptors)
    assert link_result.overall_status.value == "missing_segment"
