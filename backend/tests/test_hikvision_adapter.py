"""Tests for the Hikvision adapter: Track A (Phase 19) bounded-search raw-
filesystem detection, and Track B (Phase 26) capability/identity honesty
using synthetic-only fixtures. Track A fixtures are explicitly synthetic,
built from the *documented* "HIKVISION@HANGZHOU" signature (peer-reviewed
2015 paper + independent MIT-licensed corroboration -- see
app.adapters.hikvision's module docstring), never presented as real
Hikvision evidence. Track B behavior against REAL evidence is covered
separately in test_hikvision_real_evidence_integration.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.base import (
    AdapterCapability,
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


def test_adapter_declares_track_a_and_track_b_capabilities() -> None:
    """Phase 26: Track A (raw filesystem, unchanged) is still declared
    alongside Track B's real, exported-clip capabilities -- but RECOVERY
    is deliberately never declared for either track (see
    app.adapters.hikvision.recovery's module docstring)."""
    adapter = HikvisionAdapter()
    assert AdapterCapability.FILESYSTEM_DETECTION in adapter.capabilities
    assert AdapterCapability.RECORDING_ENUMERATION in adapter.capabilities
    assert AdapterCapability.METADATA_EXTRACTION in adapter.capabilities
    assert AdapterCapability.RECORDING_EXTRACTION in adapter.capabilities
    assert AdapterCapability.RECOVERY not in adapter.capabilities


def test_adapter_support_level_reflects_track_b_validation() -> None:
    """Phase 26: the adapter's own `support_level` reports Track B's real,
    validated status -- Track A's own still-unvalidated status is spelled
    out honestly in `model_scope`/`limitations` instead of dragging the
    whole adapter down to Track A's level (see HikvisionAdapter.
    support_level's own docstring)."""
    adapter = HikvisionAdapter()
    assert adapter.support_level == SupportLevel.LEVEL_4_VALIDATED
    assert "TRACK A" in adapter.model_scope
    assert "TRACK B" in adapter.model_scope
    assert any("TRACK A" in limitation for limitation in adapter.limitations)


def test_adapter_evidence_basis_includes_real_project_evidence() -> None:
    """Phase 26: Track B is validated against real, controlled evidence --
    this is the first time this adapter can honestly cite
    `REAL_PROJECT_EVIDENCE` (Track A remains public-research-only, see
    `model_scope`)."""
    adapter = HikvisionAdapter()
    assert EvidenceBasis.REAL_PROJECT_EVIDENCE in adapter.evidence_basis
    assert EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION in adapter.evidence_basis


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


def test_enumerate_recordings_without_reader_raises_value_error() -> None:
    adapter = HikvisionAdapter()
    with pytest.raises(ValueError, match="no bound evidence reader"):
        adapter.enumerate_recordings()


def test_enumerate_recordings_on_non_hikvision_evidence_reports_unsupported(
    tmp_path: Path,
) -> None:
    """Phase 26: a file that is neither Hikvision-named nor Hikvision-
    sidecar-confirmed is honestly UNSUPPORTED, never guessed."""
    path = _write(tmp_path, "some_random_video.mp4", b"\x00" * 1024)
    reader = FileBackedReader(path)
    adapter = HikvisionAdapter(reader)
    result = adapter.enumerate_recordings()
    assert result.confidence == 0.0
    assert result.recordings == []


def test_extract_recording_on_non_hikvision_evidence_reports_zero_confidence(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, "some_random_video.mp4", b"\x00" * 1024)
    reader = FileBackedReader(path)
    adapter = HikvisionAdapter(reader)
    result = adapter.extract_recording("does-not-exist")
    assert result.confidence == 0.0


def test_find_deleted_recordings_reports_unsupported_for_exported_media() -> None:
    """No deleted-record recovery capability is claimed for Hikvision
    exported media -- see app.adapters.hikvision.recovery's module
    docstring for why this genuinely differs from a bare "not
    implemented"."""
    adapter = HikvisionAdapter()
    result = adapter.find_deleted_recordings()
    assert result.confidence == 0.0
    assert "not_supported_for_exported_media" in result.warnings[0]


def test_minimum_inspectable_size_is_documented() -> None:
    assert MINIMUM_INSPECTABLE_SIZE > 0
