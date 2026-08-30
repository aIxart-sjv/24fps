"""
Hikvision adapter data model (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names HIKVISION /
Hikvision).

RESEARCH-EVIDENCE STATUS
-------------------------
No real Hikvision evidence exists in this project. Everything here is
built from PUBLIC RESEARCH -- `EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION`
(a peer-reviewed academic paper) and `EvidenceBasis.
PUBLIC_REFERENCE_IMPLEMENTATION` (an inspected, MIT-licensed open-source
parser) -- never `EvidenceBasis.REAL_PROJECT_EVIDENCE`. Capped at
`SupportLevel.LEVEL_1_DETECTION`. See `app.adapters.hikvision`'s module
docstring for the full research summary and citations.

Sources for the signature below:

1. Han, J. et al., "Analysis of the HIKVISION DVR File System" (IFIP
   Advances in Information and Communication Technology, Springer,
   2015) -- the original peer-reviewed academic description of the
   Hikvision proprietary filesystem's "Master Sector", which documents
   the "HIKVISION@HANGZHOU" ASCII signature as its identifying marker.
2. `akira7799/hikvision-dvr-parser` (GitHub, MIT license, inspected) --
   an independent open-source implementation that also detects
   "HIKVISION@HANGZHOU", explicitly implementing "dynamic Master Sector
   detection" because the signature's exact byte offset varies by
   firmware/model (its own README reports finding it at offset 0x30
   within the Master Sector on its one tested DVR, firmware
   `HIK.2011.03.08` -- predating source 1's own paper). This directly
   corroborates source 1's signature string while also documenting that
   no single fixed absolute offset can be trusted across firmware
   versions.

Because the offset itself is firmware-dependent (per source 2's own
explicit finding) rather than fixed, `detect_hikvision_structure`
performs a bounded *search* for the signature within a documented scan
window, rather than checking one fixed offset -- this is still a
deterministic, evidence-backed check (task Phase 19 scope: "Do not
create generic signatures like 'contains vendor name somewhere' unless
the format documentation proves this is deterministic" -- this is not
"contains the vendor name anywhere in the file", it is "contains this
exact 19-byte proprietary structural marker within the documented
Master-Sector-containing region of the disk", which two independent
sources describe as the real, structural detection mechanism).

This module only encodes the signature bytes (a fact, not copyrightable
expression) -- no code was copied from either source. `detector.py`
answers only "does this evidence contain the documented Hikvision
filesystem marker?" -- it does not parse HIKBTREE recording-index
entries, the embedded SQLite metadata database, or any recording
structure (Level 2+, not implemented -- both sources also report
structural differences across firmware/versions, e.g. different HIKBTREE
entry sizes, that this project has no way to validate without real or
authoritative sample evidence).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HikvisionParseStatus(str, Enum):
    """Outcome of a Hikvision detection operation. Mirrors
    `app.adapters.dahua.models.DahuaParseStatus`'s vocabulary shape --
    detection-only, so no `SUPPORTED_CORRUPTED` state is offered
    (distinguishing "corrupted Hikvision filesystem" from "not Hikvision
    at all" requires structural understanding this adapter does not
    claim)."""

    SUPPORTED_VALID = "supported_valid"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HikvisionSignature:
    """One documented Hikvision structural signature, searched for within
    a bounded window rather than checked at one fixed offset -- see this
    module's docstring for why (the offset is firmware-dependent per the
    open-source reference implementation's own finding)."""

    label: str
    magic: bytes
    #: How far into the evidence the signature may legitimately appear.
    #: Bounds the search so this remains a forensically-safe bounded
    #: read, never an unbounded scan of a multi-terabyte image.
    search_window: int
    minimum_container_size: int


#: "HIKVISION@HANGZHOU" -- the 19-byte ASCII Master Sector signature
#: documented by Han et al. 2015 and independently corroborated by
#: `akira7799/hikvision-dvr-parser`.
HIKVISION_MASTER_SECTOR_MAGIC = b"HIKVISION@HANGZHOU"

#: Per source 1, the Master Sector itself begins at disk offset 0x200
#: (512) and is 256 bytes long. Per source 2, the signature's position
#: *within* whatever sector holds it also varies by firmware (observed at
#: 0x30 within that sector on one real device). To stay honestly bounded
#: without hardcoding one offset neither source can guarantee is
#: universal, the search window covers generous slack around the
#: documented Master Sector location -- large enough to catch the
#: documented case and plausible firmware variance, small enough to
#: remain a bounded forensic read (never unbounded disk scanning).
HIKVISION_SEARCH_WINDOW = 8192

KNOWN_HIKVISION_SIGNATURES: tuple[HikvisionSignature, ...] = (
    HikvisionSignature(
        label="HIKVISION@HANGZHOU-mastersector",
        magic=HIKVISION_MASTER_SECTOR_MAGIC,
        search_window=HIKVISION_SEARCH_WINDOW,
        # Smaller than the documented Master Sector's own start offset
        # (512) plus its 256-byte body cannot contain it at all.
        minimum_container_size=512 + 256,
    ),
)


@dataclass(frozen=True)
class HikvisionDetectionResult:
    """Result of `app.adapters.hikvision.detector.detect_hikvision_structure`.
    Shape mirrors the other Phase 19 adapters' detection results."""

    status: HikvisionParseStatus
    matched_signature: str | None
    matched_offset: int | None
    reason: str
    evidence_size: int
    bytes_inspected: int
    warnings: list[str] | None = None
