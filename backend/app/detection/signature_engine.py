"""
Byte-signature matching primitives for storage/filesystem detection.
Master Specification Section 13 ("Device Identification": "known byte
signatures", "partition layout", "filesystem/superblock signatures") and
Section 14 ("Filesystem Detection").

Every signature here is a publicly documented, standard, non-proprietary
structure — the MBR partition table and a handful of common filesystem
boot-sector/superblock markers. Nothing here encodes any vendor-specific
DVR/NVR knowledge; that is Phase 7+ vendor-adapter territory. The EWF/E01
container signature is deliberately not reimplemented here — it is already
verified by `pyewf.check_file_signature` in `app.acquisition.e01_handler`
(Tech Stack Section 2: "We absolutely should not implement E01 ourselves").
"""

from __future__ import annotations

from dataclasses import dataclass

# --- MBR partition table (standard, non-proprietary; GPT is not supported) ---

MBR_SIGNATURE_OFFSET = 510
MBR_SIGNATURE = b"\x55\xaa"
MBR_PARTITION_TABLE_OFFSET = 446
MBR_PARTITION_ENTRY_SIZE = 16
MBR_PARTITION_ENTRY_COUNT = 4

# --- Common filesystem signatures, at their standard documented offsets ---

_EXT_MAGIC_OFFSET = 1024 + 56  # superblock starts at byte 1024; s_magic at offset 56 within it
_EXT_MAGIC = b"\x53\xef"

_NTFS_OEM_ID_OFFSET = 3
_NTFS_OEM_ID = b"NTFS    "

_EXFAT_OEM_ID_OFFSET = 3
_EXFAT_OEM_ID = b"EXFAT   "

_FAT32_LABEL_OFFSET = 82
_FAT32_LABEL = b"FAT32   "

_FAT16_LABEL_OFFSET = 54
_FAT16_LABELS = (b"FAT16   ", b"FAT12   ")

# Bytes needed from the start of a region to run every check above.
FILESYSTEM_SCAN_WINDOW = 2048


@dataclass(frozen=True)
class PartitionTableEntry:
    """One non-empty entry from a standard MBR partition table."""

    index: int
    partition_type: int
    start_sector: int
    sector_count: int


def detect_filesystem_signature(header: bytes) -> str | None:
    """Identify a filesystem from a header window starting at a region's first byte.

    Args:
        header: Bytes read from the start of the region being inspected
            (a whole device or one partition). Ideally at least
            `FILESYSTEM_SCAN_WINDOW` bytes; shorter input simply yields no
            match for checks it can't reach, never a fabricated one.

    Returns:
        One of `"ext2_3_4"`, `"ntfs"`, `"exfat"`, `"fat32"`, `"fat16"`, or
        `None` if nothing matched.
    """
    if _matches(header, _EXT_MAGIC_OFFSET, _EXT_MAGIC):
        return "ext2_3_4"
    if _matches(header, _NTFS_OEM_ID_OFFSET, _NTFS_OEM_ID):
        return "ntfs"
    if _matches(header, _EXFAT_OEM_ID_OFFSET, _EXFAT_OEM_ID):
        return "exfat"
    if _matches(header, _FAT32_LABEL_OFFSET, _FAT32_LABEL):
        return "fat32"
    if len(header) >= _FAT16_LABEL_OFFSET + 8:
        candidate = header[_FAT16_LABEL_OFFSET : _FAT16_LABEL_OFFSET + 8]
        if candidate in _FAT16_LABELS:
            return "fat16"
    return None


def _matches(header: bytes, offset: int, signature: bytes) -> bool:
    end = offset + len(signature)
    return len(header) >= end and header[offset:end] == signature


def detect_mbr_partition_table(header: bytes) -> list[PartitionTableEntry] | None:
    """Parse a standard MBR partition table if the boot signature is present.

    Args:
        header: At least 512 bytes read from the start of the device.

    Returns:
        A list of non-empty partition entries (`partition_type != 0`),
        possibly empty if the signature is present but no partitions are
        defined, or `None` if the 0x55AA boot signature is absent (either
        because there is no MBR, or `header` is too short to tell).
    """
    if len(header) < 512:
        return None
    if header[MBR_SIGNATURE_OFFSET : MBR_SIGNATURE_OFFSET + 2] != MBR_SIGNATURE:
        return None

    entries: list[PartitionTableEntry] = []
    for index in range(MBR_PARTITION_ENTRY_COUNT):
        entry_offset = MBR_PARTITION_TABLE_OFFSET + index * MBR_PARTITION_ENTRY_SIZE
        entry = header[entry_offset : entry_offset + MBR_PARTITION_ENTRY_SIZE]
        partition_type = entry[4]
        if partition_type == 0:
            continue
        start_sector = int.from_bytes(entry[8:12], "little")
        sector_count = int.from_bytes(entry[12:16], "little")
        entries.append(
            PartitionTableEntry(
                index=index,
                partition_type=partition_type,
                start_sector=start_sector,
                sector_count=sector_count,
            )
        )
    return entries
