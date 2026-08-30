"""
Dahua deterministic structure detection (Phase 19).

Mirrors `app.adapters.cp_plus.detector`'s pattern exactly: read one
bounded header window and nothing else, check it against
`KNOWN_DAHUA_SIGNATURES`, never guess. The only difference from CP Plus's
detector is the optional frame-type-byte check `DahuaSignature` supports
(see its own docstring) -- everything else (bounded read, structured
result, honest UNSUPPORTED/UNKNOWN) is the same contract.

This module answers exactly one question: "does this evidence's header
match a publicly documented Dahua container signature?" It does not parse
recording index/channel/timestamp structure (Level 2+, not implemented --
see `app.adapters.dahua`'s module docstring for why).
"""

from __future__ import annotations

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.dahua.models import (
    KNOWN_DAHUA_SIGNATURES,
    DahuaDetectionResult,
    DahuaParseStatus,
)

#: Bounded header read size -- generous enough to cover every signature's
#: `header_offset + len(magic)` plus its type-byte check, analogous to
#: `app.adapters.cp_plus.detector.DETECTION_HEADER_WINDOW`.
DETECTION_HEADER_WINDOW = 4096

#: A container smaller than this cannot hold any recognizable structure.
MINIMUM_INSPECTABLE_SIZE = 32


def detect_dahua_structure(reader: EvidenceStorageReader) -> DahuaDetectionResult:
    """Inspect a bounded header window of `reader` for a known Dahua signature.

    Args:
        reader: An already-open `EvidenceStorageReader`. Not closed here
            -- the caller owns its lifecycle.

    Returns:
        A `DahuaDetectionResult`. Always structured, never raises for a
        malformed/truncated/empty input.
    """
    size = reader.size()

    if size < MINIMUM_INSPECTABLE_SIZE:
        return DahuaDetectionResult(
            status=DahuaParseStatus.UNKNOWN,
            matched_signature=None,
            reason=(
                f"evidence container is {size} bytes, smaller than the "
                f"{MINIMUM_INSPECTABLE_SIZE}-byte minimum any recognizable structure could "
                "occupy; no reliable signal is possible"
            ),
            evidence_size=size,
            bytes_inspected=0,
        )

    window = min(DETECTION_HEADER_WINDOW, size)
    try:
        header = reader.read(0, window)
    except OSError as exc:
        return DahuaDetectionResult(
            status=DahuaParseStatus.UNKNOWN,
            matched_signature=None,
            reason="header could not be read from the evidence source",
            warnings=[f"read error at offset 0, length {window}: {exc}"],
            evidence_size=size,
            bytes_inspected=0,
        )

    for signature in KNOWN_DAHUA_SIGNATURES:
        if size < signature.minimum_container_size:
            continue
        end = signature.header_offset + len(signature.magic)
        if end > len(header):
            continue
        if header[signature.header_offset : end] != signature.magic:
            continue
        if signature.type_byte_offset is not None:
            type_offset = signature.type_byte_offset
            if type_offset >= len(header):
                continue
            if header[type_offset] not in signature.allowed_type_bytes:
                continue
        return DahuaDetectionResult(
            status=DahuaParseStatus.SUPPORTED_VALID,
            matched_signature=signature.label,
            reason=f"matched documented Dahua signature {signature.label!r}",
            evidence_size=size,
            bytes_inspected=len(header),
        )

    reason = (
        f"{len(KNOWN_DAHUA_SIGNATURES)} documented Dahua signature(s) are registered "
        f"({', '.join(sig.label for sig in KNOWN_DAHUA_SIGNATURES)}), but none matched this "
        "evidence's header; this may be Dahua evidence in a different container variant than "
        "any signature documented so far, or evidence from an unrelated vendor -- this "
        "adapter does not guess beyond publicly documented structure, and none of these "
        "signatures have been validated against real Dahua evidence in this project"
    )
    return DahuaDetectionResult(
        status=DahuaParseStatus.UNSUPPORTED,
        matched_signature=None,
        reason=reason,
        evidence_size=size,
        bytes_inspected=len(header),
    )
