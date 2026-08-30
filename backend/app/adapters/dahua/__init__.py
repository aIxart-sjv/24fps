"""
Dahua Technology vendor adapter (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names Dahua
Technology first among the eight NTRO-named OEMs).

============================================================================
RESEARCH SUMMARY -- read before touching `capabilities`/`support_level`
============================================================================
No real Dahua evidence exists in this project. Everything here is built
from PUBLIC RESEARCH (`EvidenceBasis.PUBLIC_REFERENCE_IMPLEMENTATION` +
`EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION`), never
`EvidenceBasis.REAL_PROJECT_EVIDENCE`, and is capped at
`SupportLevel.LEVEL_1_DETECTION` -- deterministic container-signature
recognition only. No recording index, channel, or timestamp structure is
parsed by this adapter.

Layer separation (this project's docs/SIH_NTRO_REQUIREMENTS.md Section
"2. The three layers we need to separate" -- storage filesystem vs.
recording/container format vs. codec are three different things):

  Layer 1 (storage filesystem):  Dahua's DHFS-family proprietary storage
                                   architecture on the raw HDD/disk image.
                                   NOT researched or implemented here --
                                   no public documentation of DHFS's own
                                   on-disk layout was found with
                                   sufficient independent corroboration
                                   to encode a signature for it.
  Layer 2 (recording container): DAV/DHAV framing -- THIS is what
                                   `detector.py` recognizes.
  Layer 3 (codec):               H.264/H.265 inside the DHAV frames --
                                   not decoded by this adapter (Level 2+
                                   territory; would reuse the project's
                                   existing FFmpeg infrastructure, per
                                   `app.media`, exactly like CP Plus does
                                   for its own H.265/H.264 muxing).

Do not conflate an exported `.dav`/`.mp4` file with proprietary native
HDD storage -- this adapter only recognizes the DAV/DHAV *container*
layer; it says nothing about Dahua's underlying DHFS storage
architecture, which remains entirely unresearched here.

============================================================================
SOURCES CONSULTED (with what each one actually established)
============================================================================
1. FFmpeg `libavformat/dhav.c` (LGPL-2.1+, copyright Paul B Mahol 2018) --
   https://github.com/FFmpeg/FFmpeg/blob/master/libavformat/dhav.c
   An actively-maintained, independently-tested, widely-deployed reference
   implementation already part of this project's own FFmpeg dependency
   (`app.media`). Its `dhav_probe()` function is the direct source for
   both signatures in `app.adapters.dahua.models.KNOWN_DAHUA_SIGNATURES`
   and for the documented per-frame header field layout referenced in
   this docstring (type/subtype/channel/frame_number/frame_length/date/
   timestamp fields at fixed offsets after the "DHAV" magic) -- this
   adapter does not reproduce that C parsing code, only the two magic
   byte facts needed for detection.
2. smlx.dev, "Dahua NVR DAV files" (third-party technical write-up) --
   https://smlx.dev/posts/dahua-pvr-files/
   Independently documents the same 5-byte "DAHUA" outer file magic from
   direct file inspection (hex `44 41 48 55 41`), corroborating source 1
   without having been derived from it. Explicitly notes ffmpeg cannot
   mux DAV directly into an MP4 container compatible with common players
   (MKV remux works) -- i.e. even with FFmpeg's native DHAV demuxer,
   producing a standard derived artifact still requires the same kind of
   remux step CP Plus's own adapter already performs for its H.265/H.264
   streams.
3. MDPI 2025 peer-reviewed study, "Automated Forensic Recovery
   Methodology for Video Evidence from Hikvision and Dahua DVR/NVR
   Systems" -- https://www.mdpi.com/2078-2489/16/11/983
   Names "DHFS4.1" as Dahua's proprietary filesystem generation and
   reports results against 27 real surveillance HDDs (91.8% recovery,
   96.7% temporal accuracy) -- strong evidence that the underlying
   storage/recording reconstruction problem is real and has been solved
   by others, but this paper's own binary-level DHFS4.1/DHAV parsing
   logic was not available to inspect or adapt (no accompanying public
   source repository was found), so it could not be used as a
   reference *implementation* here -- only as format-existence
   documentation (`EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION`).
4. `docs/SIH_NTRO_REQUIREMENTS.md` (this project's own prior research,
   sections "8. Dahua -- a second major example" and "9. Dahua also
   demonstrates why container != filesystem") -- summarizes source 3 and
   frames the DHFS-vs-DAV/DHAV distinction this docstring repeats above.

============================================================================
WHY LEVEL 1, NOT HIGHER
============================================================================
- FFmpeg's own demuxer (source 1) is real, tested software -- but this
  adapter has never actually run it against a real or even synthetic DHAV
  file in this project (no Dahua evidence, real or sample, was available)
  and does not claim it has. Reaching Level 2/3 would require
  demonstrating actual frame/index parsing or extraction against
  *something* concrete, not just citing that FFmpeg can theoretically do
  it.
- The DHFS storage-filesystem layer (where recordings actually live on a
  native HDD/disk image, as opposed to an already-exported .dav file) has
  no corroborated public byte-signature this adapter could encode
  responsibly.
- No license/attribution obligation blocks reuse here: nothing from
  FFmpeg's C source is copied, only the two documented magic-byte facts
  (facts and short byte constants are not copyrightable expression), so
  no LGPL notice obligation applies to this Python detection code. FFmpeg
  itself continues to be used strictly as an external subprocess
  (`app.media`), exactly as already established for CP Plus -- never
  linked or vendored into this codebase.

============================================================================
PATH TO UPGRADE (Phase 19 task scope: "Design every vendor adapter so
real evidence can be integrated later")
============================================================================
    current: public research (FFmpeg dhav.c + smlx.dev + MDPI paper)
                         |
                         v
             DahuaAdapter.support_level == LEVEL_1_DETECTION
                         |
             (real or authoritative sample Dahua .dav/.dhav evidence
              becomes available)
                         |
                         v
    verify detector.py's signatures against real bytes
                         |
                         v
    if FFmpeg's native `dhav` demuxer can actually extract usable media
    from that evidence (via `app.media`, same pattern as CP Plus's
    H.265/H.264 muxing), implement enumerate_recordings/extract_recording
                         |
                         v
    add real-evidence tests, then raise support_level to LEVEL_3/LEVEL_4

No architectural rewrite is required for this upgrade path -- only new
evidence, new tests, and filling in the currently-unimplemented
`DVRAdapter` operation methods this class already inherits defaults for.
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
from app.adapters.dahua.detector import DETECTION_HEADER_WINDOW, detect_dahua_structure
from app.adapters.dahua.models import (
    KNOWN_DAHUA_SIGNATURES,
    DahuaDetectionResult,
    DahuaParseStatus,
    DahuaSignature,
)

#: Not derived from any DVR's own firmware -- this is this adapter
#: implementation's own version, mirroring `app.adapters.cp_plus.parser.
#: PARSER_VERSION`'s role.
ADAPTER_VERSION = "0.1.0-research"

__all__ = [
    "ADAPTER_VERSION",
    "DETECTION_HEADER_WINDOW",
    "KNOWN_DAHUA_SIGNATURES",
    "DahuaAdapter",
    "DahuaDetectionResult",
    "DahuaParseStatus",
    "DahuaSignature",
    "detect_dahua_structure",
]


class DahuaAdapter(DVRAdapter):
    """Vendor-level Dahua adapter -- detection only (`SupportLevel.
    LEVEL_1_DETECTION`). See this module's docstring for the full
    research basis and why this is capped where it is.

    Two usage modes, matching `app.adapters.cp_plus.CPPlusAdapter`'s own
    established split:

      - Constructed with no `reader` (`DahuaAdapter()`): identity-only,
        what an `AdapterRegistry` holds for matching.
      - Constructed with a `reader`: the form a caller uses to actually
        run `inspect_storage()` against bound evidence.
    """

    def __init__(self, reader: EvidenceStorageReader | None = None) -> None:
        self._reader = reader

    @property
    def vendor(self) -> str:
        return "Dahua Technology"

    @property
    def model_pattern(self) -> str:
        # Vendor-level generic adapter: no specific Dahua model/firmware
        # has been validated (there is no real Dahua evidence in this
        # project at all) -- see module docstring.
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
            EvidenceBasis.PUBLIC_REFERENCE_IMPLEMENTATION,
            EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION,
        )

    @property
    def model_scope(self) -> str:
        return (
            "no specific Dahua model/firmware validated; signatures are generic "
            "DAV/DHAV container markers documented independently by FFmpeg's dhav.c "
            "demuxer and a third-party technical write-up -- see module docstring"
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "no real or sample Dahua evidence has been tested against this adapter in "
            "this project -- REAL VALIDATION PENDING",
            "only the DAV/DHAV recording-container layer is recognized; Dahua's "
            "underlying DHFS-family storage filesystem is not researched or detected",
            "recording index/channel/timestamp structure is not parsed (Level 2+, not "
            "implemented)",
            "media extraction is not implemented; FFmpeg's own native DHAV demuxer is a "
            "documented, plausible extraction path once real evidence is available, but "
            "this has not been exercised in this project",
        )

    def inspect_storage(self) -> AdapterResult:
        """Run Dahua container-signature detection against the bound evidence reader."""
        if self._reader is None:
            raise ValueError(
                "this DahuaAdapter instance has no bound evidence reader; construct "
                "DahuaAdapter(reader=...) to run detection (the no-reader form is for "
                "AdapterRegistry selection only)"
            )
        detection = detect_dahua_structure(self._reader)
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format=detection.matched_signature,
            capability_set=self.capabilities,
            recordings=[],
            metadata={},
            recovery_candidates=[],
            warnings=[*(detection.warnings or []), detection.reason],
            parser_version=self.adapter_version,
            confidence=1.0 if detection.status == DahuaParseStatus.SUPPORTED_VALID else 0.0,
        )

    def parse_filesystem(self) -> AdapterResult:
        """Alias for `inspect_storage`: no distinct filesystem-parsing stage is
        implemented (Level 1 is detection-only)."""
        return self.inspect_storage()
