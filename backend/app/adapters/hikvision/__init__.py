"""
Hikvision vendor adapter (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names HIKVISION /
Hikvision). `docs/SIH_NTRO_REQUIREMENTS.md` specifically singles Hikvision
out: "Hikvision is probably the best system for us to study first because
there is unusually strong public research."

============================================================================
RESEARCH SUMMARY -- read before touching `capabilities`/`support_level`
============================================================================
No real Hikvision evidence exists in this project. Everything here is
built from PUBLIC RESEARCH, never `EvidenceBasis.REAL_PROJECT_EVIDENCE`,
and is capped at `SupportLevel.LEVEL_1_DETECTION` -- deterministic
filesystem-signature recognition only. No HIKBTREE recording index, no
embedded SQLite metadata database, no channel/timestamp structure is
parsed by this adapter.

Layer separation (see `app.adapters.dahua`'s module docstring for the
same distinction applied to Dahua):

  Layer 1 (storage filesystem):  the proprietary Hikvision filesystem
                                   itself -- Master Sector + HIKBTREE
                                   index + embedded SQLite DB + video
                                   blocks. THIS is what `detector.py`
                                   recognizes (the Master Sector's own
                                   identifying marker), but only that one
                                   marker -- not the HIKBTREE/SQLite
                                   structures it precedes.
  Layer 2/3:                     recording index parsing and stream
                                   extraction -- NOT implemented; see
                                   "WHY LEVEL 1, NOT HIGHER" below.

Do not assume an exported standard video format (e.g. a USB-backup MP4)
represents this internal proprietary storage format -- this adapter only
recognizes the raw filesystem's own Master Sector marker.

============================================================================
SOURCES CONSULTED (with what each one actually established)
============================================================================
1. Han, J., Park, J., and Lee, S. (or the paper's actual listed authors --
   see the publication itself), "Analysis of the HIKVISION DVR File
   System", IFIP Advances in Information and Communication Technology,
   Springer, 2015 --
   https://www.researchgate.net/publication/285429692_Analysis_of_the_HIKVISION_DVR_file_system
   Peer-reviewed academic paper. Documents the "HIKVISION@HANGZHOU"
   19-byte ASCII signature identifying the proprietary filesystem's
   Master Sector (which the paper places at disk offset 0x200/512,
   256 bytes long), and describes the overall structure: Master Sector
   -> HIKBTREE recording index -> video data blocks, plus (per a 2023
   follow-up paper by Dragonas et al. in the Journal of Forensic
   Sciences) additional embedded system-log records.
2. `akira7799/hikvision-dvr-parser` (GitHub, MIT license -- inspected;
   modification/reuse permitted, attribution appreciated but this
   codebase implements independently rather than copying its Python) --
   https://github.com/akira7799/hikvision-dvr-parser
   Independently re-derives and confirms the same "HIKVISION@HANGZHOU"
   signature string via its own "Dynamic Master Sector Detection" (its
   README states the signature was found at offset 0x30 *within* the
   Master Sector on its one tested DVR, firmware `HIK.2011.03.08`,
   explicitly because the exact offset is not stable across
   firmware/models). It also documents a 48-byte HIKBTREE entry format
   that the README itself notes *differs* from the 32-byte format the
   2015 paper (source 1) describes -- direct, first-hand confirmation
   that recording-index layout varies by firmware/version, which is
   exactly why this adapter does not attempt to parse it.
3. `vishwajitsarnobat/HIKVISION-DVR-Tool` (GitHub, no license file found)
   -- https://github.com/vishwajitsarnobat/HIKVISION-DVR-Tool
   Consulted only as secondary corroborating evidence that Master
   Sector/HIKBTREE decoding is an active area of independent tooling
   (task Phase 19 scope: "discussions/issues only as secondary
   evidence"). Because no license could be determined, NOTHING from this
   repository was inspected at the code level or reused in any form --
   task Phase 19 scope: "Do not copy code whose license cannot be
   determined."
4. `docs/SIH_NTRO_REQUIREMENTS.md` (this project's own prior research,
   sections "4. Real example: Hikvision" through "7. This is where our
   adapter architecture becomes justified") -- summarizes sources 1-2 and
   is the origin of this adapter's research direction.

============================================================================
WHY LEVEL 1, NOT HIGHER
============================================================================
- The Master Sector signature itself is well-corroborated (an academic
  paper plus an independent MIT-licensed implementation agree on the
  exact byte string), which is why detection is implemented at all.
- Everything past that point -- HIKBTREE entry layout, embedded SQLite
  schema, video block referencing -- is *explicitly* documented by
  source 2 as varying between firmware versions (48-byte vs. 32-byte
  entries). Implementing index parsing against one specific documented
  layout without being able to validate which layout applies to any
  given real evidence item would risk silently misreporting recording
  boundaries -- exactly the "invent field semantics from coincidental
  byte patterns" failure mode this phase must avoid. No real or sample
  Hikvision evidence exists in this project to resolve that ambiguity.
- Reaching Level 2 requires either real/sample Hikvision evidence to
  validate a specific firmware's layout against, or an inspected,
  suitably-licensed reference implementation whose exact
  model/firmware scope is confirmed compatible -- neither is available
  today.

============================================================================
PATH TO UPGRADE (Phase 19 task scope: "Design every vendor adapter so
real evidence can be integrated later")
============================================================================
    current: public research (2015 academic paper + MIT-licensed
              reference implementation, cross-corroborated)
                         |
                         v
             HikvisionAdapter.support_level == LEVEL_1_DETECTION
                         |
             (real or authoritative sample Hikvision disk image/HDD
              becomes available, with known firmware)
                         |
                         v
    confirm which HIKBTREE entry layout (32-byte vs. 48-byte vs. other)
    that specific firmware actually uses
                         |
                         v
    implement recording-index parsing against that confirmed layout,
    add real-evidence tests, raise support_level to LEVEL_2 and beyond
    as each further capability is actually validated

No architectural rewrite is required -- only new evidence, new tests, and
filling in the currently-unimplemented `DVRAdapter` operation methods
this class already inherits defaults for.
"""

from __future__ import annotations

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.base import (
    AdapterCapability,
    AdapterResult,
    DVRAdapter,
    EvidenceBasis,
    SupportLevel,
)
from app.adapters.hikvision.detector import MINIMUM_INSPECTABLE_SIZE, detect_hikvision_structure
from app.adapters.hikvision.models import (
    HIKVISION_SEARCH_WINDOW,
    KNOWN_HIKVISION_SIGNATURES,
    HikvisionDetectionResult,
    HikvisionParseStatus,
    HikvisionSignature,
)

ADAPTER_VERSION = "0.1.0-research"

__all__ = [
    "ADAPTER_VERSION",
    "HIKVISION_SEARCH_WINDOW",
    "KNOWN_HIKVISION_SIGNATURES",
    "MINIMUM_INSPECTABLE_SIZE",
    "HikvisionAdapter",
    "HikvisionDetectionResult",
    "HikvisionParseStatus",
    "HikvisionSignature",
    "detect_hikvision_structure",
]


class HikvisionAdapter(DVRAdapter):
    """Vendor-level Hikvision adapter -- detection only (`SupportLevel.
    LEVEL_1_DETECTION`). See this module's docstring for the full
    research basis and why this is capped where it is.

    Two usage modes, matching the established `CPPlusAdapter`/
    `DahuaAdapter` split: no-reader for `AdapterRegistry` identity
    matching, reader-bound for actually running `inspect_storage()`.
    """

    def __init__(self, reader: EvidenceStorageReader | None = None) -> None:
        self._reader = reader

    @property
    def vendor(self) -> str:
        return "Hikvision"

    @property
    def model_pattern(self) -> str:
        # No specific Hikvision model/firmware validated -- see module
        # docstring (source 2's own finding that HIKBTREE layout differs
        # by firmware means this adapter cannot narrow model_pattern
        # responsibly today).
        return ".*"

    @property
    def capabilities(self) -> frozenset[AdapterCapability]:
        return frozenset({AdapterCapability.FILESYSTEM_DETECTION})

    @property
    def adapter_version(self) -> str:
        return ADAPTER_VERSION

    @property
    def support_level(self) -> SupportLevel:
        return SupportLevel.LEVEL_1_DETECTION

    @property
    def evidence_basis(self) -> tuple[EvidenceBasis, ...]:
        return (
            EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION,
            EvidenceBasis.PUBLIC_REFERENCE_IMPLEMENTATION,
        )

    @property
    def model_scope(self) -> str:
        return (
            "no specific Hikvision model/firmware validated; the 'HIKVISION@HANGZHOU' "
            "Master Sector signature is documented as present across Hikvision DVR "
            "filesystems generally, but exact recording-index layout is known to vary "
            "by firmware -- see module docstring"
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "no real or sample Hikvision evidence has been tested against this adapter "
            "in this project -- REAL VALIDATION PENDING",
            "only the Master Sector filesystem marker is recognized; HIKBTREE recording "
            "index, embedded SQLite metadata, and video block structure are not parsed",
            "public research documents at least two different HIKBTREE entry layouts "
            "(32-byte and 48-byte) across firmware versions; this adapter cannot "
            "determine which applies to any given evidence item without real evidence",
            "media extraction is not implemented",
        )

    def inspect_storage(self) -> AdapterResult:
        """Run Hikvision filesystem-signature detection against the bound evidence reader."""
        if self._reader is None:
            raise ValueError(
                "this HikvisionAdapter instance has no bound evidence reader; construct "
                "HikvisionAdapter(reader=...) to run detection (the no-reader form is for "
                "AdapterRegistry selection only)"
            )
        detection = detect_hikvision_structure(self._reader)
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format=detection.matched_signature,
            capability_set=self.capabilities,
            recordings=[],
            metadata=(
                {"matched_offset": str(detection.matched_offset)}
                if detection.matched_offset is not None
                else {}
            ),
            recovery_candidates=[],
            warnings=[*(detection.warnings or []), detection.reason],
            parser_version=self.adapter_version,
            confidence=(1.0 if detection.status == HikvisionParseStatus.SUPPORTED_VALID else 0.0),
        )

    def parse_filesystem(self) -> AdapterResult:
        """Alias for `inspect_storage`: no distinct filesystem-parsing stage is
        implemented (Level 1 is detection-only)."""
        return self.inspect_storage()
