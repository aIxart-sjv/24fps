"""Tests for app.detection.identify_evidence, the Phase 6 orchestrator."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from app.acquisition import e01_handler
from app.detection import identify_evidence
from app.schemas.device import IdentificationStatus

pyewf = pytest.importorskip("pyewf", reason="libewf-python (pyewf) is not installed")


def _e01_write_supported() -> bool:
    """Probe whether this pyewf build can write EWF segments (needs zlib).

    Mirrors the identical probe in tests/test_e01_reader.py — kept
    self-contained here rather than imported, matching this repo's
    convention of self-contained test modules.
    """
    scratch = Path(tempfile.mkdtemp())
    try:
        handle = pyewf.handle()
        handle.open([str(scratch / "probe.E01")], "w")
        handle.close()
        return True
    except OSError:
        return False
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


_WRITE_SUPPORTED = _e01_write_supported()
_SKIP_REASON = (
    "this environment's pyewf build was compiled without zlib/write support; cannot generate "
    "a real E01 fixture to identify"
)


def test_identifies_raw_dd_by_declared_source_type(tmp_path: Path):
    path = tmp_path / "image.dd"
    path.write_bytes(b"\x00" * 4096)

    result = identify_evidence("raw_dd", path)

    assert result.status == IdentificationStatus.PARTIAL
    assert result.storage_format == "raw_dd"
    assert result.device_type == "storage_media"
    assert result.identification_method == "explicit_metadata"


def test_identifies_filesystem_signature_within_raw_dd(tmp_path: Path):
    buf = bytearray(4096)
    buf[1024 + 56 : 1024 + 58] = b"\x53\xef"
    path = tmp_path / "image.dd"
    path.write_bytes(bytes(buf))

    result = identify_evidence("raw_dd", path)

    assert result.filesystem_type == "ext2_3_4"
    assert "ext2_3_4" in result.parser_selection_hints


def test_generic_file_with_no_signal_is_unknown(tmp_path: Path):
    path = tmp_path / "export.mp4"
    path.write_bytes(b"not a real video, just bytes")

    result = identify_evidence("video_file", path)

    assert result.status == IdentificationStatus.UNKNOWN
    assert result.confidence == 0.0
    assert result.vendor is None


def test_directory_source_yields_structured_unknown_not_a_crash(tmp_path: Path):
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    (export_dir / "recording.mp4").write_bytes(b"data")

    result = identify_evidence("native_export", export_dir)

    assert result.status == IdentificationStatus.PARTIAL
    assert result.device_type == "export"
    assert any("directory" in w for w in result.warnings)


def test_missing_file_yields_structured_unknown_not_a_crash(tmp_path: Path):
    result = identify_evidence("raw_dd", tmp_path / "does_not_exist.dd")

    assert result.status in (IdentificationStatus.UNKNOWN, IdentificationStatus.PARTIAL)
    assert any(w for w in result.warnings)


def test_truncated_below_mbr_size_does_not_crash(tmp_path: Path):
    """A file too short even for a single 512-byte MBR sector must not error."""
    path = tmp_path / "tiny.dd"
    path.write_bytes(b"\x00" * 10)

    result = identify_evidence("raw_dd", path)

    assert result.status == IdentificationStatus.PARTIAL
    assert result.filesystem_type is None


def test_e01_declared_but_invalid_signature_is_unsupported_not_silently_raw(tmp_path: Path):
    fake = tmp_path / "fake.E01"
    fake.write_bytes(b"this is not a real EWF file" * 20)

    result = identify_evidence("e01", fake)

    assert result.status == IdentificationStatus.UNSUPPORTED
    assert result.confidence == 0.0
    assert result.storage_format == "e01"
    assert any("signature" in w.lower() for w in result.warnings)
    # Must never claim a filesystem/format was actually determined.
    assert result.filesystem_type is None


def test_e01_unavailable_libewf_is_unsupported_not_silently_raw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(e01_handler, "pyewf", None)
    fake = tmp_path / "image.E01"
    fake.write_bytes(b"placeholder")

    result = identify_evidence("e01", fake)

    assert result.status == IdentificationStatus.UNSUPPORTED
    assert result.confidence == 0.0
    assert any("libewf" in w.lower() for w in result.warnings)


def test_never_infers_vendor_from_source_description_or_filename(tmp_path: Path):
    """A suggestive filename must never be treated as identification evidence."""
    path = tmp_path / "hikvision_cp_plus_dahua_export.dd"
    path.write_bytes(b"\x00" * 4096)

    result = identify_evidence("raw_dd", path)

    assert result.vendor is None
    assert result.model is None


@pytest.mark.skipif(not _WRITE_SUPPORTED, reason=_SKIP_REASON)
def test_identifies_real_e01_container_with_full_confidence(tmp_path: Path):
    target = tmp_path / "sample"
    data = (b"24FPS-PHASE6-E01-TEST-" * 50)[:1200]

    handle = pyewf.handle()
    handle.open([str(target) + ".E01"], "w")
    handle.set_media_size(len(data))
    handle.write(data)
    handle.close()

    result = identify_evidence("e01", target.with_suffix(".E01"))

    assert result.status == IdentificationStatus.IDENTIFIED
    assert result.confidence == 1.0
    assert result.storage_format == "e01"
    assert result.identification_method == "container_signature"
    assert result.capacity == len(data)
    assert "e01" in result.parser_selection_hints
