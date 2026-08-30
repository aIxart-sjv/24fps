"""
Dahua adapter data model (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters").

RESEARCH-EVIDENCE STATUS
-------------------------
No real Dahua evidence exists in this project (unlike CP Plus). Everything
here is built from PUBLIC RESEARCH, cross-corroborated across independent
sources, and is explicitly `SupportLevel.LEVEL_1_DETECTION` --
`EvidenceBasis.PUBLIC_REFERENCE_IMPLEMENTATION` +
`EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION`, never
`REAL_PROJECT_EVIDENCE`. See `app.adapters.dahua`'s module docstring for
the full research summary and every source cited.

Sources for the two signatures below (independently corroborating each
other -- see the package docstring for full citations):

1. FFmpeg's own `dhav.c` demuxer (`libavformat/dhav.c`, LGPL-2.1+,
   copyright Paul B Mahol 2018, actively maintained as part of the
   FFmpeg project this codebase already depends on for media handling)
   -- its `dhav_probe()` function checks for exactly the two patterns
   encoded below. This is the strongest available public evidence: a
   widely-deployed, independently-tested reference implementation, not a
   single blog's guess.
2. An independent third-party technical write-up (smlx.dev, "Dahua NVR
   DAV files") that separately documents the same "DAHUA" 5-byte outer
   file magic from direct file inspection.

Only the outer/frame *magic bytes* are encoded here (facts: fixed byte
values at fixed offsets) -- this module does not reproduce FFmpeg's C
parsing logic, header-field layout code, or any other copyrightable
expression from that source. `detector.py` only ever answers "does this
evidence match a documented Dahua container signature?" -- it does not
parse frame headers, channel/timestamp fields, or recording structure.
That would require `SupportLevel.LEVEL_2_STRUCTURE_PARSING`, which this
adapter does not claim (see `app.adapters.dahua`'s module docstring).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DahuaParseStatus(str, Enum):
    """Outcome of a Dahua detection operation. Mirrors
    `app.adapters.cp_plus.models.CPPlusParseStatus`'s vocabulary shape,
    but this adapter only ever produces the subset a detection-only
    (Level 1) capability can honestly report -- it never claims
    `SUPPORTED_CORRUPTED` (that requires understanding enough of the
    structure to tell "corrupted" apart from "different format
    entirely", which is Level 2+ territory)."""

    SUPPORTED_VALID = "supported_valid"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DahuaSignature:
    """One documented Dahua container structural signature.

    `type_byte_offset`/`allowed_type_bytes` are optional because the
    "DAHUA" outer-file signature is a plain fixed-byte match, while the
    per-frame "DHAV" signature additionally requires the byte immediately
    after the 4-byte magic to be one of a documented small set of frame
    types (FFmpeg's `dhav_probe`: 0xf0, 0xf1, 0xfc, 0xfd) -- a single
    frozen magic-bytes-at-offset field cannot express that second
    constraint, so both fields are optional and only checked when
    `type_byte_offset` is not `None`.
    """

    label: str
    header_offset: int
    magic: bytes
    minimum_container_size: int
    type_byte_offset: int | None = None
    allowed_type_bytes: frozenset[int] = frozenset()


#: "DAHUA" -- the 5-byte outer file magic, documented independently by
#: FFmpeg's `dhav_probe()` (returns `AVPROBE_SCORE_MAX` for this exact
#: byte string at offset 0) and by the smlx.dev technical write-up (hex
#: `44 41 48 55 41`). This is the outer-file-header form.
DAHUA_OUTER_MAGIC = b"DAHUA"

#: "DHAV" -- the 4-byte per-frame magic FFmpeg also accepts directly at
#: file start (for raw, header-less multi-frame streams), when followed
#: by one of the four documented frame-type bytes.
DHAV_FRAME_MAGIC = b"DHAV"

#: The exact frame-type byte values FFmpeg's `dhav_probe()` checks for at
#: the byte immediately following the "DHAV" magic (offset 4).
DHAV_FRAME_TYPE_BYTES: frozenset[int] = frozenset({0xF0, 0xF1, 0xFC, 0xFD})

KNOWN_DAHUA_SIGNATURES: tuple[DahuaSignature, ...] = (
    DahuaSignature(
        label="DAHUA-outer-v1",
        header_offset=0,
        magic=DAHUA_OUTER_MAGIC,
        # 8 bytes is the smallest span both cited sources describe before
        # any real per-frame data would need to follow.
        minimum_container_size=8,
    ),
    DahuaSignature(
        label="DHAV-frame-v1",
        header_offset=0,
        magic=DHAV_FRAME_MAGIC,
        minimum_container_size=24,  # documented fixed frame-header size
        type_byte_offset=4,
        allowed_type_bytes=DHAV_FRAME_TYPE_BYTES,
    ),
)


@dataclass(frozen=True)
class DahuaDetectionResult:
    """Result of `app.adapters.dahua.detector.detect_dahua_structure`.
    Shape deliberately mirrors `app.adapters.cp_plus.models.
    CPPlusDetectionResult` for consistency across adapters."""

    status: DahuaParseStatus
    matched_signature: str | None
    reason: str
    evidence_size: int
    bytes_inspected: int
    warnings: list[str] | None = None
