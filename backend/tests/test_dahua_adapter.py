"""Tests for the Dahua adapter (Phase 19): detection, capability
reporting, support-level honesty. All fixtures are explicitly synthetic,
built from the *documented* byte layout (FFmpeg's dhav.c probe function
+ independent corroboration -- see app.adapters.dahua's module
docstring), never presented as real Dahua evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.base import AdapterCapability, EvidenceBasis, SupportLevel
from app.adapters.dahua import DahuaAdapter
from app.adapters.dahua.detector import (
    DETECTION_HEADER_WINDOW,
    MINIMUM_INSPECTABLE_SIZE,
    detect_dahua_structure,
)
from app.adapters.dahua.models import DahuaParseStatus


def _write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


# ---- Signature detection ---------------------------------------------


def test_detects_dahua_outer_magic(tmp_path: Path) -> None:
    path = _write(tmp_path, "outer.dav", b"DAHUA\x22\x05\x00" + b"\x00" * 64)
    reader = FileBackedReader(path)
    result = detect_dahua_structure(reader)
    assert result.status == DahuaParseStatus.SUPPORTED_VALID
    assert result.matched_signature == "DAHUA-outer-v1"


def test_detects_dhav_frame_magic_with_valid_type_byte(tmp_path: Path) -> None:
    path = _write(tmp_path, "frame.dav", b"DHAV" + bytes([0xFD]) + b"\x00" * 40)
    reader = FileBackedReader(path)
    result = detect_dahua_structure(reader)
    assert result.status == DahuaParseStatus.SUPPORTED_VALID
    assert result.matched_signature == "DHAV-frame-v1"


@pytest.mark.parametrize("type_byte", [0xF0, 0xF1, 0xFC, 0xFD])
def test_all_documented_frame_type_bytes_match(tmp_path: Path, type_byte: int) -> None:
    path = _write(tmp_path, "frame.dav", b"DHAV" + bytes([type_byte]) + b"\x00" * 40)
    reader = FileBackedReader(path)
    result = detect_dahua_structure(reader)
    assert result.status == DahuaParseStatus.SUPPORTED_VALID


def test_dhav_magic_with_undocumented_type_byte_does_not_match(tmp_path: Path) -> None:
    path = _write(tmp_path, "frame.dav", b"DHAV" + bytes([0x00]) + b"\x00" * 40)
    reader = FileBackedReader(path)
    result = detect_dahua_structure(reader)
    assert result.status == DahuaParseStatus.UNSUPPORTED


def test_unrelated_content_reports_unsupported(tmp_path: Path) -> None:
    path = _write(tmp_path, "other.bin", b"NOT_DAHUA_AT_ALL" * 4)
    reader = FileBackedReader(path)
    result = detect_dahua_structure(reader)
    assert result.status == DahuaParseStatus.UNSUPPORTED
    assert result.matched_signature is None
    assert "does not guess" in result.reason


def test_empty_evidence_reports_unknown(tmp_path: Path) -> None:
    path = _write(tmp_path, "empty.bin", b"")
    reader = FileBackedReader(path)
    result = detect_dahua_structure(reader)
    assert result.status == DahuaParseStatus.UNKNOWN
    assert result.evidence_size == 0


def test_truncated_evidence_below_minimum_reports_unknown(tmp_path: Path) -> None:
    path = _write(tmp_path, "tiny.bin", b"D")
    reader = FileBackedReader(path)
    result = detect_dahua_structure(reader)
    assert result.status == DahuaParseStatus.UNKNOWN


def test_malformed_evidence_never_raises(tmp_path: Path) -> None:
    """A corrupt/malformed input must produce a controlled result, never crash."""
    path = _write(tmp_path, "malformed.bin", b"\xff" * 10 + b"DAHUA" + b"\x00" * 5)
    reader = FileBackedReader(path)
    result = detect_dahua_structure(reader)
    assert result.status in (
        DahuaParseStatus.UNSUPPORTED,
        DahuaParseStatus.UNKNOWN,
        DahuaParseStatus.SUPPORTED_VALID,
    )


def test_detection_read_is_bounded(tmp_path: Path) -> None:
    """A large evidence file must never be read in full -- only the
    bounded detection header window."""
    large_content = b"DAHUA\x22\x05\x00" + b"\x00" * (10 * 1024 * 1024)
    path = _write(tmp_path, "large.dav", large_content)
    reader = FileBackedReader(path)
    result = detect_dahua_structure(reader)
    assert result.bytes_inspected <= DETECTION_HEADER_WINDOW
    assert result.status == DahuaParseStatus.SUPPORTED_VALID


# ---- Adapter identity / honesty ----------------------------------------


def test_adapter_declares_detection_only_capability() -> None:
    adapter = DahuaAdapter()
    assert adapter.capabilities == frozenset({AdapterCapability.FILESYSTEM_DETECTION})
    # Never claims extraction/recovery/metadata capability it does not implement.
    assert AdapterCapability.RECORDING_EXTRACTION not in adapter.capabilities
    assert AdapterCapability.RECOVERY not in adapter.capabilities
    assert AdapterCapability.RECORDING_ENUMERATION not in adapter.capabilities


def test_adapter_support_level_is_detection_not_validated() -> None:
    adapter = DahuaAdapter()
    assert adapter.support_level == SupportLevel.LEVEL_1_DETECTION
    assert adapter.support_level < SupportLevel.LEVEL_4_VALIDATED


def test_adapter_evidence_basis_is_never_real_project_evidence() -> None:
    adapter = DahuaAdapter()
    assert EvidenceBasis.REAL_PROJECT_EVIDENCE not in adapter.evidence_basis
    assert len(adapter.evidence_basis) > 0


def test_adapter_limitations_are_never_empty() -> None:
    adapter = DahuaAdapter()
    assert len(adapter.limitations) > 0
    assert any("REAL VALIDATION PENDING" in lim for lim in adapter.limitations)


def test_adapter_vendor_identity() -> None:
    adapter = DahuaAdapter()
    assert adapter.vendor == "Dahua Technology"
    assert adapter.model_pattern == ".*"


def test_inspect_storage_without_reader_raises_value_error() -> None:
    adapter = DahuaAdapter()
    with pytest.raises(ValueError):
        adapter.inspect_storage()


def test_inspect_storage_with_reader_returns_structured_result(tmp_path: Path) -> None:
    path = _write(tmp_path, "outer.dav", b"DAHUA\x22\x05\x00" + b"\x00" * 64)
    reader = FileBackedReader(path)
    adapter = DahuaAdapter(reader)
    result = adapter.inspect_storage()
    assert result.vendor == "Dahua Technology"
    assert result.confidence == 1.0
    assert result.detected_format == "DAHUA-outer-v1"


def test_enumerate_recordings_is_not_implemented() -> None:
    """Level 1 (detection only) never claims recording enumeration."""
    from app.adapters.base import AdapterCapabilityNotImplementedError

    adapter = DahuaAdapter()
    with pytest.raises(AdapterCapabilityNotImplementedError):
        adapter.enumerate_recordings()


def test_extract_recording_is_not_implemented() -> None:
    from app.adapters.base import AdapterCapabilityNotImplementedError

    adapter = DahuaAdapter()
    with pytest.raises(AdapterCapabilityNotImplementedError):
        adapter.extract_recording("anything")


def test_minimum_inspectable_size_is_documented() -> None:
    assert MINIMUM_INSPECTABLE_SIZE > 0
