"""
Storage / filesystem structure identification.
Master Specification Section 14 ("Filesystem Detection"):

    "RAW storage -> partition/layout analysis -> signature scan ->
    filesystem/format candidate -> vendor/model/firmware correlation ->
    adapter selection -> parser. If unsupported: status =
    unknown_or_unsupported. The system should flag unsupported formats
    instead of inventing a structure."

This module performs the first three steps of that pipeline only —
partition/layout analysis and signature scanning down to a filesystem/
format candidate. Vendor correlation and adapter selection are Phase 6's
device_identifier module and Phase 7 respectively; this module knows
nothing about either.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.acquisition.storage_reader import EvidenceStorageReader
from app.detection.signature_engine import (
    FILESYSTEM_SCAN_WINDOW,
    detect_filesystem_signature,
    detect_mbr_partition_table,
)


@dataclass(frozen=True)
class PartitionDetectionResult:
    """One detected partition and, where determinable, its filesystem type."""

    index: int
    partition_type: int
    start_sector: int
    sector_count: int
    filesystem_type: str | None


@dataclass(frozen=True)
class StorageDetectionResult:
    """Everything `detect_storage_structure` could determine about a container."""

    storage_format: str
    sector_size: int
    capacity: int
    filesystem_type: str | None
    partitions: list[PartitionDetectionResult] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)


def detect_storage_structure(reader: EvidenceStorageReader) -> StorageDetectionResult:
    """Inspect a bounded header window of `reader` for known storage structures.

    Only reads `FILESYSTEM_SCAN_WINDOW` bytes at a time (plus the same
    bounded window per detected partition) — never the whole container —
    so this stays usable against multi-terabyte evidence (Master
    Specification Section 60: "Do not load a multi-terabyte image entirely
    into RAM").

    Args:
        reader: An already-open `EvidenceStorageReader`. Not closed here —
            the caller owns its lifecycle.

    Returns:
        A `StorageDetectionResult` describing what was found. A container
        with no recognized filesystem or partition table still yields a
        valid result (`filesystem_type=None`, empty `partitions`) — that
        is a legitimate outcome, not an error.
    """
    metadata = reader.metadata()
    sector_size = int(metadata.get("sector_size") or 512)
    capacity = reader.size()
    storage_format = str(metadata.get("format", "unknown"))
    supporting_evidence: list[str] = [f"reader format: {storage_format}"]

    header = reader.read(0, FILESYSTEM_SCAN_WINDOW)

    mbr_entries = detect_mbr_partition_table(header)
    partitions: list[PartitionDetectionResult] = []
    filesystem_type: str | None

    if mbr_entries is not None and mbr_entries:
        supporting_evidence.append(
            f"MBR partition table detected ({len(mbr_entries)} partition(s))"
        )
        # A partitioned disk has no single whole-device filesystem; each
        # partition is inspected independently below.
        filesystem_type = None
        for entry in mbr_entries:
            partition_offset = entry.start_sector * sector_size
            partition_header = (
                reader.read(partition_offset, FILESYSTEM_SCAN_WINDOW)
                if partition_offset < capacity
                else b""
            )
            partition_fs = detect_filesystem_signature(partition_header)
            partitions.append(
                PartitionDetectionResult(
                    index=entry.index,
                    partition_type=entry.partition_type,
                    start_sector=entry.start_sector,
                    sector_count=entry.sector_count,
                    filesystem_type=partition_fs,
                )
            )
            supporting_evidence.append(
                f"partition {entry.index}: type=0x{entry.partition_type:02x}, "
                f"start_sector={entry.start_sector}, sector_count={entry.sector_count}, "
                f"filesystem={partition_fs or 'unknown'}"
            )
    else:
        filesystem_type = detect_filesystem_signature(header)
        if filesystem_type is not None:
            supporting_evidence.append(f"filesystem signature matched: {filesystem_type}")

    return StorageDetectionResult(
        storage_format=storage_format,
        sector_size=sector_size,
        capacity=capacity,
        filesystem_type=filesystem_type,
        partitions=partitions,
        supporting_evidence=supporting_evidence,
    )
