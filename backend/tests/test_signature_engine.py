"""Tests for the pure byte-signature primitives in app.detection.signature_engine."""

from __future__ import annotations

import pytest

from app.detection.signature_engine import (
    FILESYSTEM_SCAN_WINDOW,
    detect_filesystem_signature,
    detect_mbr_partition_table,
)


def _window(patches: dict[int, bytes], size: int = FILESYSTEM_SCAN_WINDOW) -> bytes:
    """Build a zero-filled header window with specific byte patches applied."""
    buf = bytearray(size)
    for offset, value in patches.items():
        buf[offset : offset + len(value)] = value
    return bytes(buf)


# --- filesystem signature detection ---


def test_detects_ext_magic():
    header = _window({1024 + 56: b"\x53\xef"})
    assert detect_filesystem_signature(header) == "ext2_3_4"


def test_detects_ntfs_oem_id():
    header = _window({3: b"NTFS    "})
    assert detect_filesystem_signature(header) == "ntfs"


def test_detects_exfat_oem_id():
    header = _window({3: b"EXFAT   "})
    assert detect_filesystem_signature(header) == "exfat"


def test_detects_fat32_label():
    header = _window({82: b"FAT32   "})
    assert detect_filesystem_signature(header) == "fat32"


@pytest.mark.parametrize("label", [b"FAT16   ", b"FAT12   "])
def test_detects_fat16_family_labels(label: bytes):
    header = _window({54: label})
    assert detect_filesystem_signature(header) == "fat16"


def test_deterministic_non_matching_data_yields_no_match():
    """A predictable, non-random byte pattern that hits none of the known
    signature offsets must not spuriously match anything."""
    header = bytes(range(256)) * (FILESYSTEM_SCAN_WINDOW // 256)
    assert detect_filesystem_signature(header) is None


def test_all_zero_buffer_yields_no_match():
    assert detect_filesystem_signature(bytes(FILESYSTEM_SCAN_WINDOW)) is None


def test_empty_header_yields_no_match_not_an_error():
    assert detect_filesystem_signature(b"") is None


def test_short_header_below_every_offset_yields_no_match():
    assert detect_filesystem_signature(b"\x00" * 10) is None


def test_signature_at_wrong_offset_does_not_match():
    """A signature byte sequence placed at the wrong offset must not match."""
    header = _window({100: b"NTFS    "})  # correct offset is 3, not 100
    assert detect_filesystem_signature(header) is None


# --- MBR partition table ---


def _mbr_entry(partition_type: int, start_sector: int, sector_count: int) -> bytes:
    entry = bytearray(16)
    entry[4] = partition_type
    entry[8:12] = start_sector.to_bytes(4, "little")
    entry[12:16] = sector_count.to_bytes(4, "little")
    return bytes(entry)


def test_detects_valid_mbr_with_one_partition():
    header = _window(
        {
            446: _mbr_entry(0x83, 2048, 204800),
            510: b"\x55\xaa",
        }
    )
    entries = detect_mbr_partition_table(header)
    assert entries is not None
    assert len(entries) == 1
    assert entries[0].partition_type == 0x83
    assert entries[0].start_sector == 2048
    assert entries[0].sector_count == 204800
    assert entries[0].index == 0


def test_detects_multiple_mbr_partitions_and_skips_empty_entries():
    header = _window(
        {
            446: _mbr_entry(0x83, 2048, 100),
            446 + 32: _mbr_entry(0x07, 3000, 200),  # skip entry 1 (left empty/type 0)
            510: b"\x55\xaa",
        }
    )
    entries = detect_mbr_partition_table(header)
    assert entries is not None
    assert [e.index for e in entries] == [0, 2]


def test_missing_boot_signature_yields_no_mbr():
    header = _window({446: _mbr_entry(0x83, 2048, 100)})  # no 0x55AA at 510
    assert detect_mbr_partition_table(header) is None


def test_mbr_signature_present_but_no_partitions_yields_empty_list():
    header = _window({510: b"\x55\xaa"})
    entries = detect_mbr_partition_table(header)
    assert entries == []


def test_mbr_detection_requires_at_least_512_bytes():
    assert detect_mbr_partition_table(b"\x55\xaa") is None
    assert detect_mbr_partition_table(bytes(511)) is None
