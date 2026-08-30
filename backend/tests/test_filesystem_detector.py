"""Tests for app.detection.filesystem_detector.detect_storage_structure."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.acquisition.raw_imager import RawDDReader
from app.acquisition.storage_reader import FileBackedReader
from app.detection.filesystem_detector import detect_storage_structure


def _mbr_entry(partition_type: int, start_sector: int, sector_count: int) -> bytes:
    entry = bytearray(16)
    entry[4] = partition_type
    entry[8:12] = start_sector.to_bytes(4, "little")
    entry[12:16] = sector_count.to_bytes(4, "little")
    return bytes(entry)


def test_reports_reader_format_sector_size_and_capacity(tmp_path: Path):
    content = b"\x00" * 4096
    path = tmp_path / "image.dd"
    path.write_bytes(content)

    reader = RawDDReader(path, sector_size=512)
    try:
        result = detect_storage_structure(reader)
    finally:
        reader.close()

    assert result.storage_format == "raw_dd"
    assert result.sector_size == 512
    assert result.capacity == len(content)
    assert result.filesystem_type is None
    assert result.partitions == []


def test_detects_unpartitioned_filesystem_signature(tmp_path: Path):
    buf = bytearray(4096)
    buf[1024 + 56 : 1024 + 58] = b"\x53\xef"  # ext magic
    path = tmp_path / "image.dd"
    path.write_bytes(bytes(buf))

    reader = RawDDReader(path, sector_size=512)
    try:
        result = detect_storage_structure(reader)
    finally:
        reader.close()

    assert result.filesystem_type == "ext2_3_4"
    assert result.partitions == []
    assert any("filesystem signature matched" in s for s in result.supporting_evidence)


def test_detects_mbr_and_per_partition_filesystem(tmp_path: Path):
    sector_size = 512
    total_sectors = 20
    buf = bytearray(sector_size * total_sectors)

    # One partition starting at sector 4, containing an ext filesystem.
    buf[446:462] = _mbr_entry(0x83, 4, 10)
    buf[510:512] = b"\x55\xaa"
    partition_offset = 4 * sector_size
    buf[partition_offset + 1024 + 56 : partition_offset + 1024 + 58] = b"\x53\xef"

    path = tmp_path / "disk.dd"
    path.write_bytes(bytes(buf))

    reader = RawDDReader(path, sector_size=sector_size)
    try:
        result = detect_storage_structure(reader)
    finally:
        reader.close()

    # A partitioned disk has no single whole-device filesystem.
    assert result.filesystem_type is None
    assert len(result.partitions) == 1
    partition = result.partitions[0]
    assert partition.partition_type == 0x83
    assert partition.start_sector == 4
    assert partition.sector_count == 10
    assert partition.filesystem_type == "ext2_3_4"
    assert any("MBR partition table detected" in s for s in result.supporting_evidence)


def test_partition_beyond_capacity_is_reported_without_reading_out_of_bounds(tmp_path: Path):
    """A corrupt/truncated MBR pointing past the device's own size must not crash."""
    sector_size = 512
    buf = bytearray(sector_size * 4)  # tiny 4-sector image

    # Partition claims to start far beyond the actual (truncated) image size.
    buf[446:462] = _mbr_entry(0x83, 100_000, 10)
    buf[510:512] = b"\x55\xaa"

    path = tmp_path / "truncated.dd"
    path.write_bytes(bytes(buf))

    reader = RawDDReader(path, sector_size=sector_size)
    try:
        result = detect_storage_structure(reader)
    finally:
        reader.close()

    assert len(result.partitions) == 1
    assert result.partitions[0].filesystem_type is None


def test_no_signatures_yields_unknown_but_valid_result(tmp_path: Path):
    path = tmp_path / "plain.bin"
    path.write_bytes(b"just some ordinary file bytes, not a filesystem")

    reader = FileBackedReader(path)
    try:
        result = detect_storage_structure(reader)
    finally:
        reader.close()

    assert result.filesystem_type is None
    assert result.partitions == []
    assert result.storage_format == "file"


def test_only_reads_bounded_window_not_entire_large_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Detection must not load a large evidence file entirely into memory."""
    path = tmp_path / "huge.dd"
    # Sparse-ish large file: only need its declared size to be large: write
    # via seek to avoid actually allocating real disk blocks for the body.
    with path.open("wb") as f:
        f.seek(50 * 1024 * 1024 - 1)
        f.write(b"\x00")

    reader = RawDDReader(path, sector_size=512)
    read_calls: list[tuple[int, int]] = []
    original_read = reader.read

    def spying_read(offset: int, length: int) -> bytes:
        read_calls.append((offset, length))
        return original_read(offset, length)

    monkeypatch.setattr(reader, "read", spying_read)

    try:
        result = detect_storage_structure(reader)
    finally:
        reader.close()

    assert result.capacity == 50 * 1024 * 1024
    # Every individual read must be small and bounded, never the full file.
    assert all(length <= 2048 for _offset, length in read_calls)
    assert sum(length for _offset, length in read_calls) < 1024 * 1024
