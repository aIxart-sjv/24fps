"""Tests for the Hikvision adapter (Phase 19): bounded-search detection,
capability reporting, support-level honesty. All fixtures are explicitly
synthetic, built from the *documented* "HIKVISION@HANGZHOU" signature
(peer-reviewed 2015 paper + independent MIT-licensed corroboration --
see app.adapters.hikvision's module docstring), never presented as real
Hikvision evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.base import (
    AdapterCapability,
    AdapterCapabilityNotImplementedError,
    EvidenceBasis,
    SupportLevel,
)
from app.adapters.hikvision import HikvisionAdapter
from app.adapters.hikvision.detector import MINIMUM_INSPECTABLE_SIZE, detect_hikvision_structure
from app.adapters.hikvision.models import HIKVISION_SEARCH_WINDOW, HikvisionParseStatus


def _write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


# ---- Signature detection ---------------------------------------------


def test_detects_signature_at_documented_offset(tmp_path: Path) -> None:
    """The 2015 paper places the Master Sector at disk offset 0x200 (512)."""
    content = b"\x00" * 512 + b"HIKVISION@HANGZHOU" + b"\x00" * 300
    path = _write(tmp_path, "documented_offset.img", content)
    reader = FileBackedReader(path)
    result = detect_hikvision_structure(reader)
    assert result.status == HikvisionParseStatus.SUPPORTED_VALID
    assert result.matched_offset == 512


def test_detects_signature_at_firmware_variant_offset(tmp_path: Path) -> None:
    """The MIT-licensed reference implementation found the signature at
    0x30 within the Master Sector on its own tested device -- confirms
    the bounded search (not a single fixed offset) is the correct design."""
    content = b"\x00" * (512 + 0x30) + b"HIKVISION@HANGZHOU" + b"\x00" * 200
    path = _write(tmp_path, "variant_offset.img", content)
    reader = FileBackedReader(path)
    result = detect_hikvision_structure(reader)
    assert result.status == HikvisionParseStatus.SUPPORTED_VALID
    assert result.matched_offset == 512 + 0x30


def test_signature_outside_search_window_is_not_found(tmp_path: Path) -> None:
    content = b"\x00" * (HIKVISION_SEARCH_WINDOW + 100) + b"HIKVISION@HANGZHOU"
    path = _write(tmp_path, "far.img", content)
    reader = FileBackedReader(path)
    result = detect_hikvision_structure(reader)
    assert result.status == HikvisionParseStatus.UNSUPPORTED


def test_unrelated_content_reports_unsupported(tmp_path: Path) -> None:
    path = _write(tmp_path, "other.bin", b"NOT_HIKVISION_AT_ALL" * 40)
    reader = FileBackedReader(path)
    result = detect_hikvision_structure(reader)
    assert result.status == HikvisionParseStatus.UNSUPPORTED
    assert result.matched_signature is None
    assert "does not extend the search unboundedly" in result.reason


def test_empty_evidence_reports_unknown(tmp_path: Path) -> None:
    path = _write(tmp_path, "empty.bin", b"")
    reader = FileBackedReader(path)
    result = detect_hikvision_structure(reader)
    assert result.status == HikvisionParseStatus.UNKNOWN


def test_truncated_evidence_below_master_sector_reports_unsupported(tmp_path: Path) -> None:
    """Smaller than the documented Master Sector's own start+size cannot
    contain it -- but is still large enough to be inspectable, so this
    is a definitive UNSUPPORTED, not an UNKNOWN "too small to tell"."""
    path = _write(tmp_path, "small.bin", b"\x00" * 600)
    reader = FileBackedReader(path)
    result = detect_hikvision_structure(reader)
    assert result.status == HikvisionParseStatus.UNSUPPORTED


def test_malformed_evidence_never_raises(tmp_path: Path) -> None:
    content = b"\xff" * 300 + b"HIKVISION@HANGZHO" + b"\x00" * 50  # truncated magic
    path = _write(tmp_path, "malformed.bin", content)
    reader = FileBackedReader(path)
    result = detect_hikvision_structure(reader)
    assert result.status in (
        HikvisionParseStatus.UNSUPPORTED,
        HikvisionParseStatus.UNKNOWN,
        HikvisionParseStatus.SUPPORTED_VALID,
    )


def test_detection_read_is_bounded(tmp_path: Path) -> None:
    large_content = b"\x00" * 512 + b"HIKVISION@HANGZHOU" + b"\x00" * (10 * 1024 * 1024)
    path = _write(tmp_path, "large.img", large_content)
    reader = FileBackedReader(path)
    result = detect_hikvision_structure(reader)
    assert result.bytes_inspected <= HIKVISION_SEARCH_WINDOW
    assert result.status == HikvisionParseStatus.SUPPORTED_VALID


# ---- Adapter identity / honesty ----------------------------------------


def test_adapter_declares_detection_only_capability() -> None:
    adapter = HikvisionAdapter()
    assert adapter.capabilities == frozenset({AdapterCapability.FILESYSTEM_DETECTION})
    assert AdapterCapability.RECORDING_EXTRACTION not in adapter.capabilities
    assert AdapterCapability.RECOVERY not in adapter.capabilities
    assert AdapterCapability.RECORDING_ENUMERATION not in adapter.capabilities
    assert AdapterCapability.METADATA_EXTRACTION not in adapter.capabilities


def test_adapter_support_level_is_detection_not_validated() -> None:
    adapter = HikvisionAdapter()
    assert adapter.support_level == SupportLevel.LEVEL_1_DETECTION
    assert adapter.support_level < SupportLevel.LEVEL_4_VALIDATED


def test_adapter_evidence_basis_is_never_real_project_evidence() -> None:
    adapter = HikvisionAdapter()
    assert EvidenceBasis.REAL_PROJECT_EVIDENCE not in adapter.evidence_basis
    assert len(adapter.evidence_basis) > 0


def test_adapter_limitations_document_firmware_variance() -> None:
    adapter = HikvisionAdapter()
    assert len(adapter.limitations) > 0
    assert any("REAL VALIDATION PENDING" in lim for lim in adapter.limitations)
    assert any("HIKBTREE" in lim for lim in adapter.limitations)


def test_adapter_vendor_identity() -> None:
    adapter = HikvisionAdapter()
    assert adapter.vendor == "Hikvision"
    assert adapter.model_pattern == ".*"


def test_inspect_storage_without_reader_raises_value_error() -> None:
    adapter = HikvisionAdapter()
    with pytest.raises(ValueError):
        adapter.inspect_storage()


def test_inspect_storage_with_reader_returns_structured_result(tmp_path: Path) -> None:
    content = b"\x00" * 512 + b"HIKVISION@HANGZHOU" + b"\x00" * 300
    path = _write(tmp_path, "match.img", content)
    reader = FileBackedReader(path)
    adapter = HikvisionAdapter(reader)
    result = adapter.inspect_storage()
    assert result.vendor == "Hikvision"
    assert result.confidence == 1.0
    assert result.metadata["matched_offset"] == "512"


def test_enumerate_recordings_is_not_implemented() -> None:
    adapter = HikvisionAdapter()
    with pytest.raises(AdapterCapabilityNotImplementedError):
        adapter.enumerate_recordings()


def test_extract_recording_is_not_implemented() -> None:
    adapter = HikvisionAdapter()
    with pytest.raises(AdapterCapabilityNotImplementedError):
        adapter.extract_recording("anything")


def test_find_deleted_recordings_is_not_implemented() -> None:
    """No deleted-record recovery capability was claimed for Hikvision."""
    adapter = HikvisionAdapter()
    with pytest.raises(AdapterCapabilityNotImplementedError):
        adapter.find_deleted_recordings()


def test_minimum_inspectable_size_is_documented() -> None:
    assert MINIMUM_INSPECTABLE_SIZE > 0
