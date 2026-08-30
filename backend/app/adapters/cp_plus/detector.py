"""
CP Plus deterministic structure detection (Phase 8 / Fourth Backend Milestone).
Phase 8 task scope, section 2 ("CP Plus Format Detection"):

    "The parser must be able to answer: 'Does this evidence match the CP
    Plus structure this adapter understands?' If not: return a structured
    UNSUPPORTED / UNKNOWN result."

This module never guesses. It checks the evidence's bytes against
`app.adapters.cp_plus.models.KNOWN_CP_PLUS_SIGNATURES` only — no filename
inspection, no "probably CP Plus" heuristics. That tuple now holds one
validated signature ("ADIT-v1"), confirmed byte-identical across all 13
files in a real, hash-verified CP Plus evidence package — see `models.py`'s
module docstring for exactly which device/firmware it was validated
against. Evidence that does not match it (including CP Plus evidence from
a different model/firmware/export tool) still honestly reaches
`CPPlusParseStatus.UNSUPPORTED` — that is not a bug, it is this module
refusing to guess beyond what was actually validated.

Reads a single bounded header window (`DETECTION_HEADER_WINDOW` bytes) and
nothing else, so this stays safe against multi-terabyte evidence (Master
Specification Section 60), mirroring `app.detection.filesystem_detector`'s
own bounded-header approach.
"""

from __future__ import annotations

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.cp_plus.models import (
    KNOWN_CP_PLUS_SIGNATURES,
    CPPlusDetectionResult,
    CPPlusParseStatus,
)

# Bounded header read size for signature scanning — analogous to
# app.detection.signature_engine.FILESYSTEM_SCAN_WINDOW, kept as its own
# constant because CP Plus header structures (once validated) may not share
# the same generic filesystem scan window.
DETECTION_HEADER_WINDOW = 4096

# A container smaller than this cannot hold any recognizable structure at
# all — reported as UNKNOWN (no reliable signal possible), distinct from a
# well-formed-enough container that simply matches no known signature
# (UNSUPPORTED).
MINIMUM_INSPECTABLE_SIZE = 512


def detect_cp_plus_structure(reader: EvidenceStorageReader) -> CPPlusDetectionResult:
    """Inspect a bounded header window of `reader` for a known CP Plus signature.

    Args:
        reader: An already-open `EvidenceStorageReader`. Not closed here —
            the caller owns its lifecycle.

    Returns:
        A `CPPlusDetectionResult`. Always returns a structured result, even
        for an empty, truncated, or unreadable container — never raises for
        a malformed input (Phase 8 task scope, section 6: "A corrupt input
        must produce a controlled parser error/result. It must not crash
        the process.").
    """
    size = reader.size()

    if size < MINIMUM_INSPECTABLE_SIZE:
        return CPPlusDetectionResult(
            status=CPPlusParseStatus.UNKNOWN,
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
        return CPPlusDetectionResult(
            status=CPPlusParseStatus.UNKNOWN,
            matched_signature=None,
            reason="header could not be read from the evidence source",
            warnings=[f"read error at offset 0, length {window}: {exc}"],
            evidence_size=size,
            bytes_inspected=0,
        )

    for signature in KNOWN_CP_PLUS_SIGNATURES:
        if size < signature.minimum_container_size:
            continue
        end = signature.header_offset + len(signature.magic)
        if end > len(header):
            continue
        if header[signature.header_offset : end] == signature.magic:
            return CPPlusDetectionResult(
                status=CPPlusParseStatus.SUPPORTED_VALID,
                matched_signature=signature.label,
                reason=f"matched validated CP Plus signature {signature.label!r}",
                evidence_size=size,
                bytes_inspected=len(header),
            )

    if not KNOWN_CP_PLUS_SIGNATURES:
        reason = (
            "no validated CP Plus structural signature is registered in this build "
            "(0 known signatures); a real, controlled CP Plus fixture has not yet been "
            "acquired into this repository, and this adapter does not infer proprietary "
            "structure from undocumented or third-party examples"
        )
    else:
        reason = (
            f"{len(KNOWN_CP_PLUS_SIGNATURES)} validated CP Plus signature(s) are registered "
            f"({', '.join(sig.label for sig in KNOWN_CP_PLUS_SIGNATURES)}), but none matched "
            "this evidence's header; this may be CP Plus evidence from a different "
            "model/firmware/export tool than any signature validated so far, or evidence from "
            "an unrelated vendor — this adapter does not guess beyond what was validated"
        )

    return CPPlusDetectionResult(
        status=CPPlusParseStatus.UNSUPPORTED,
        matched_signature=None,
        reason=reason,
        evidence_size=size,
        bytes_inspected=len(header),
    )
