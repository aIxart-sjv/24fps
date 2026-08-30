"""
Hikvision deterministic structure detection (Phase 19).

Unlike `app.adapters.cp_plus.detector`/`app.adapters.dahua.detector`
(fixed-offset magic checks), this module performs a bounded *search* for
`HIKVISION_MASTER_SECTOR_MAGIC` within `HIKVISION_SEARCH_WINDOW` bytes --
see `app.adapters.hikvision.models`'s module docstring for why the offset
cannot be trusted as fixed across firmware. The read is still strictly
bounded (never unbounded scanning of a multi-terabyte image), and the
search itself is a plain, deterministic substring search over that one
bounded buffer -- no recursion, no unbounded loop driven by evidence
content.

This module answers only "does this evidence contain the documented
Hikvision filesystem marker?" -- it does not parse HIKBTREE/SQLite
recording-index structure (Level 2+, not implemented).
"""

from __future__ import annotations

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.hikvision.models import (
    KNOWN_HIKVISION_SIGNATURES,
    HikvisionDetectionResult,
    HikvisionParseStatus,
)

MINIMUM_INSPECTABLE_SIZE = 512


def detect_hikvision_structure(reader: EvidenceStorageReader) -> HikvisionDetectionResult:
    """Search a bounded window of `reader` for a known Hikvision signature.

    Args:
        reader: An already-open `EvidenceStorageReader`. Not closed here
            -- the caller owns its lifecycle.

    Returns:
        A `HikvisionDetectionResult`. Always structured, never raises for
        a malformed/truncated/empty input.
    """
    size = reader.size()

    if size < MINIMUM_INSPECTABLE_SIZE:
        return HikvisionDetectionResult(
            status=HikvisionParseStatus.UNKNOWN,
            matched_signature=None,
            matched_offset=None,
            reason=(
                f"evidence container is {size} bytes, smaller than the "
                f"{MINIMUM_INSPECTABLE_SIZE}-byte minimum any recognizable structure could "
                "occupy; no reliable signal is possible"
            ),
            evidence_size=size,
            bytes_inspected=0,
        )

    max_bytes_inspected = 0
    for signature in KNOWN_HIKVISION_SIGNATURES:
        if size < signature.minimum_container_size:
            continue
        window = min(signature.search_window, size)
        try:
            buffer = reader.read(0, window)
        except OSError as exc:
            return HikvisionDetectionResult(
                status=HikvisionParseStatus.UNKNOWN,
                matched_signature=None,
                matched_offset=None,
                reason="header/search window could not be read from the evidence source",
                warnings=[f"read error at offset 0, length {window}: {exc}"],
                evidence_size=size,
                bytes_inspected=0,
            )
        max_bytes_inspected = max(max_bytes_inspected, len(buffer))
        offset = buffer.find(signature.magic)
        if offset != -1:
            return HikvisionDetectionResult(
                status=HikvisionParseStatus.SUPPORTED_VALID,
                matched_signature=signature.label,
                matched_offset=offset,
                reason=(
                    f"matched documented Hikvision signature {signature.label!r} at "
                    f"offset {offset}"
                ),
                evidence_size=size,
                bytes_inspected=len(buffer),
            )

    reason = (
        f"{len(KNOWN_HIKVISION_SIGNATURES)} documented Hikvision signature(s) are registered, "
        "but none matched within the bounded search window of this evidence; this may be "
        "Hikvision evidence whose Master Sector lies outside the documented search window for "
        "this firmware, or evidence from an unrelated vendor -- this adapter does not extend "
        "the search unboundedly, and no Hikvision signature has been validated against real "
        "evidence in this project"
    )
    return HikvisionDetectionResult(
        status=HikvisionParseStatus.UNSUPPORTED,
        matched_signature=None,
        matched_offset=None,
        reason=reason,
        evidence_size=size,
        bytes_inspected=max_bytes_inspected,
    )
