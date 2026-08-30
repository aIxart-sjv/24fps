"""Tests for E01/EWF reading via `app.acquisition.e01_handler`.

Real E01 fixtures require write/compression support in the installed
`pyewf` (libewf) build to generate; some environments build `pyewf`
without zlib and therefore without write support at all (verified via
`_e01_write_supported()` below). Tests that need a real, readable E01
container skip cleanly with a clear reason in that case rather than
faking success — everything that does not require *writing* a fixture
(signature rejection, missing-file handling, the "libewf unavailable"
failure path) is exercised for real, unconditionally.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from app.acquisition import e01_handler
from app.acquisition.e01_handler import (
    E01FormatError,
    E01Reader,
    E01UnavailableError,
    is_e01_support_available,
)

pyewf = pytest.importorskip("pyewf", reason="libewf-python (pyewf) is not installed")


def _e01_write_supported() -> bool:
    """Probe whether this pyewf build can write EWF segments (needs zlib)."""
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
    "this environment's pyewf build was compiled without zlib/write support "
    "(libewf_handle_open: write access currently not supported - compiled without zlib); "
    "cannot generate a real E01 fixture to read back"
)


@pytest.fixture
def real_e01_file() -> Path:
    """A genuine, pyewf-written single-segment EWF image (only when write-capable)."""
    scratch = Path(tempfile.mkdtemp())
    target = scratch / "sample"
    data = (b"24FPS-FORENSIC-TEST-MEDIA-" * 50)[:1200]

    handle = pyewf.handle()
    handle.open([str(target) + ".E01"], "w")
    handle.set_media_size(len(data))
    handle.write(data)
    handle.close()

    yield target.with_suffix(".E01"), data
    shutil.rmtree(scratch, ignore_errors=True)


# --- Availability ---


def test_e01_support_is_available_in_this_environment():
    assert is_e01_support_available() is True


def test_e01_unavailable_error_raised_when_pyewf_missing(monkeypatch: pytest.MonkeyPatch):
    """Simulates a deployment without libewf-python: must fail clearly, not silently."""
    monkeypatch.setattr(e01_handler, "pyewf", None)
    with pytest.raises(E01UnavailableError, match="libewf-python"):
        E01Reader(Path("/nonexistent/does_not_matter.E01"))


# --- Invalid / unsupported input: must fail clearly, never silently fall back ---


def test_e01_reader_rejects_missing_file(tmp_path: Path):
    with pytest.raises(ValueError):
        E01Reader(tmp_path / "missing.E01")


def test_e01_reader_rejects_invalid_signature(tmp_path: Path):
    fake = tmp_path / "not_really.E01"
    fake.write_bytes(b"this is not an EWF file" * 20)

    with pytest.raises(E01FormatError, match="valid EWF/E01 signature"):
        E01Reader(fake)


def test_e01_reader_does_not_fall_back_to_raw_reading_on_bad_signature(tmp_path: Path):
    """An invalid E01 must raise, never be silently treated as raw bytes."""
    fake = tmp_path / "not_really.E01"
    fake.write_bytes(b"\x00" * 100)

    with pytest.raises(E01FormatError):
        reader = E01Reader(fake)
        reader.close()  # pragma: no cover - unreachable if the raise above holds


# --- Real E01 read-through (only where this environment can write a fixture) ---


@pytest.mark.skipif(not _WRITE_SUPPORTED, reason=_SKIP_REASON)
def test_e01_reader_reads_back_exact_content(real_e01_file: tuple[Path, bytes]):
    path, data = real_e01_file
    reader = E01Reader(path)
    try:
        assert reader.size() == len(data)
        assert reader.read(0, len(data)) == data
        assert reader.read(10, 20) == data[10:30]
    finally:
        reader.close()


@pytest.mark.skipif(not _WRITE_SUPPORTED, reason=_SKIP_REASON)
def test_e01_reader_metadata_reports_e01_format(real_e01_file: tuple[Path, bytes]):
    path, data = real_e01_file
    reader = E01Reader(path)
    try:
        metadata = reader.metadata()
        assert metadata["format"] == "e01"
        assert metadata["size_bytes"] == len(data)
        assert "sector_size" in metadata
        assert "acquisition_tool_metadata" in metadata
    finally:
        reader.close()


@pytest.mark.skipif(not _WRITE_SUPPORTED, reason=_SKIP_REASON)
def test_e01_reader_read_past_end_returns_partial(real_e01_file: tuple[Path, bytes]):
    path, data = real_e01_file
    reader = E01Reader(path)
    try:
        assert reader.read(len(data) - 5, 100) == data[-5:]
        assert reader.read(len(data), 10) == b""
    finally:
        reader.close()


@pytest.mark.skipif(not _WRITE_SUPPORTED, reason=_SKIP_REASON)
def test_e01_reader_operations_after_close_raise(real_e01_file: tuple[Path, bytes]):
    path, _data = real_e01_file
    reader = E01Reader(path)
    reader.close()
    with pytest.raises(ValueError, match="closed"):
        reader.read(0, 1)
