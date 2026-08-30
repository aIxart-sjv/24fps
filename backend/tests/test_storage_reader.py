"""Tests for the generic EvidenceStorageReader interface and its concrete readers."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from app.acquisition.raw_imager import RawDDReader
from app.acquisition.storage_reader import DEFAULT_SECTOR_SIZE, FileBackedReader


@pytest.fixture
def sample_file(tmp_path: Path) -> tuple[Path, bytes]:
    content = bytes(range(256)) * 20  # 5120 bytes, deterministic and varied
    path = tmp_path / "evidence.bin"
    path.write_bytes(content)
    return path, content


# --- FileBackedReader: read/size/metadata/hash contract ---


def test_read_returns_exact_slice(sample_file: tuple[Path, bytes]):
    path, content = sample_file
    reader = FileBackedReader(path)
    try:
        assert reader.read(0, 10) == content[0:10]
        assert reader.read(100, 50) == content[100:150]
    finally:
        reader.close()


def test_size_matches_file_size(sample_file: tuple[Path, bytes]):
    path, content = sample_file
    reader = FileBackedReader(path)
    try:
        assert reader.size() == len(content)
    finally:
        reader.close()


def test_metadata_contains_expected_keys(sample_file: tuple[Path, bytes]):
    path, content = sample_file
    reader = FileBackedReader(path)
    try:
        metadata = reader.metadata()
        assert metadata["format"] == "file"
        assert metadata["size_bytes"] == len(content)
        assert metadata["sector_size"] == DEFAULT_SECTOR_SIZE
        assert metadata["source_path"] == str(path.resolve())
    finally:
        reader.close()


def test_generic_file_reader_has_no_embedded_hash(sample_file: tuple[Path, bytes]):
    path, _content = sample_file
    reader = FileBackedReader(path)
    try:
        assert reader.hash() is None
    finally:
        reader.close()


def test_read_sector_uses_sector_size(sample_file: tuple[Path, bytes]):
    path, content = sample_file
    reader = FileBackedReader(path, sector_size=16)
    try:
        assert reader.read_sector(2) == content[32:48]
    finally:
        reader.close()


def test_context_manager_closes_reader(sample_file: tuple[Path, bytes]):
    path, _content = sample_file
    with FileBackedReader(path) as reader:
        assert reader.read(0, 4) is not None
    with pytest.raises(ValueError, match="closed"):
        reader.read(0, 1)


def test_close_is_idempotent(sample_file: tuple[Path, bytes]):
    path, _content = sample_file
    reader = FileBackedReader(path)
    reader.close()
    reader.close()  # must not raise


# --- Offsets and bounds ---


def test_read_past_end_of_file_returns_partial_bytes(sample_file: tuple[Path, bytes]):
    path, content = sample_file
    reader = FileBackedReader(path)
    try:
        result = reader.read(len(content) - 5, 100)
        assert result == content[-5:]
    finally:
        reader.close()


def test_read_at_exact_end_of_file_returns_empty(sample_file: tuple[Path, bytes]):
    path, content = sample_file
    reader = FileBackedReader(path)
    try:
        assert reader.read(len(content), 10) == b""
    finally:
        reader.close()


def test_read_zero_length_returns_empty(sample_file: tuple[Path, bytes]):
    path, _content = sample_file
    reader = FileBackedReader(path)
    try:
        assert reader.read(0, 0) == b""
    finally:
        reader.close()


@pytest.mark.parametrize("offset,length", [(-1, 10), (0, -1), (-5, -5)])
def test_read_rejects_negative_offset_or_length(sample_file: tuple[Path, bytes], offset, length):
    path, _content = sample_file
    reader = FileBackedReader(path)
    try:
        with pytest.raises(ValueError, match="non-negative"):
            reader.read(offset, length)
    finally:
        reader.close()


def test_read_sector_rejects_negative_sector_number(sample_file: tuple[Path, bytes]):
    path, _content = sample_file
    reader = FileBackedReader(path)
    try:
        with pytest.raises(ValueError, match="non-negative"):
            reader.read_sector(-1)
    finally:
        reader.close()


def test_operations_after_close_raise(sample_file: tuple[Path, bytes]):
    path, _content = sample_file
    reader = FileBackedReader(path)
    reader.close()
    with pytest.raises(ValueError, match="closed"):
        reader.read(0, 1)


# --- Read-only behavior ---


def test_reading_never_mutates_the_source_file(sample_file: tuple[Path, bytes]):
    """A full read pass through the reader must leave the source file untouched."""
    path, content = sample_file
    before_mode = stat.S_IMODE(os.stat(path).st_mode)
    before_mtime = os.stat(path).st_mtime_ns

    reader = FileBackedReader(path)
    try:
        offset = 0
        while offset < reader.size():
            chunk = reader.read(offset, 37)  # odd chunk size to exercise repeated seeks
            offset += len(chunk)
        reader.read_sector(0)
    finally:
        reader.close()

    assert path.read_bytes() == content
    assert stat.S_IMODE(os.stat(path).st_mode) == before_mode
    assert os.stat(path).st_mtime_ns == before_mtime


def test_reader_interface_exposes_no_write_method():
    """The abstraction itself must not offer any mutating operation."""
    public_methods = {name for name in dir(FileBackedReader) if not name.startswith("_")}
    assert not any("write" in name for name in public_methods)


# --- Invalid construction ---


def test_reader_rejects_missing_file(tmp_path: Path):
    with pytest.raises(ValueError):
        FileBackedReader(tmp_path / "does_not_exist.bin")


def test_reader_rejects_directory(tmp_path: Path):
    with pytest.raises(ValueError):
        FileBackedReader(tmp_path)


def test_reader_rejects_non_positive_sector_size(sample_file: tuple[Path, bytes]):
    path, _content = sample_file
    with pytest.raises(ValueError, match="sector_size"):
        FileBackedReader(path, sector_size=0)


# --- Large-file / chunked reads ---


def test_chunked_reads_reconstruct_full_content(tmp_path: Path):
    content = os.urandom(1_000_003)  # deliberately not a round chunk multiple
    path = tmp_path / "large.bin"
    path.write_bytes(content)

    reader = FileBackedReader(path)
    chunks: list[bytes] = []
    try:
        chunk_size = 65536
        offset = 0
        while offset < reader.size():
            chunk = reader.read(offset, chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
            offset += len(chunk)
    finally:
        reader.close()

    assert b"".join(chunks) == content


# --- RawDDReader ---


def test_raw_dd_reader_reports_raw_dd_format(sample_file: tuple[Path, bytes]):
    path, content = sample_file
    reader = RawDDReader(path, sector_size=512)
    try:
        metadata = reader.metadata()
        assert metadata["format"] == "raw_dd"
        assert metadata["sector_size"] == 512
        assert reader.size() == len(content)
        assert reader.read(0, len(content)) == content
    finally:
        reader.close()


def test_raw_dd_reader_sector_access(tmp_path: Path):
    sector_size = 512
    data = os.urandom(sector_size * 4)
    path = tmp_path / "image.dd"
    path.write_bytes(data)

    reader = RawDDReader(path, sector_size=sector_size)
    try:
        assert reader.read_sector(2) == data[sector_size * 2 : sector_size * 3]
        assert reader.hash() is None
    finally:
        reader.close()


def test_raw_dd_reader_rejects_missing_file(tmp_path: Path):
    with pytest.raises(ValueError):
        RawDDReader(tmp_path / "missing.dd")
