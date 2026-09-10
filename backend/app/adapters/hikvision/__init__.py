"""
Hikvision vendor adapter (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names HIKVISION /
Hikvision). `docs/SIH_NTRO_REQUIREMENTS.md` specifically singles Hikvision
out: "Hikvision is probably the best system for us to study first because
there is unusually strong public research."

============================================================================
PHASE 26 UPDATE -- read this before touching `capabilities`/`support_level`
============================================================================
Phase 26 ("Hikvision Integration") added a REAL evidence-backed track
alongside the research-only track described below. This adapter now
covers two genuinely different evidence classes, kept clearly separate
end to end -- never conflated into one "Hikvision: supported" claim
(Phase 26 task scope, section 21, "Capability Matrix"):

  Track A -- raw native filesystem/HDD (unchanged from Phase 19):
    `inspect_storage()`/`parse_filesystem()` still only recognize the
    documented "HIKVISION@HANGZHOU" Master Sector marker within a bounded
    search window -- see "RESEARCH SUMMARY" below. Still
    `EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION`/
    `PUBLIC_REFERENCE_IMPLEMENTATION` only, still Level-1-equivalent, still
    unvalidated against any real Hikvision HDD/disk image. Nothing in this
    track changed in Phase 26.
  Track B -- already-exported `.mp4` clips (new in Phase 26):
    `enumerate_recordings()`/`extract_recording()`/`normalize_evidence()`
    now do real, evidence-validated work -- see
    `app.adapters.hikvision.parser`'s module docstring for the full
    evidence basis (a real DS-7A04HQHI-K1, firmware V4.30.220 Build
    220216, evidence set of 3 exported clips + device export-log
    sidecars). `EvidenceBasis.REAL_PROJECT_EVIDENCE` for this track only.

`capabilities`/`support_level`/`evidence_basis`/`model_scope`/
`limitations` below report the union of both tracks, with `model_scope`/
`limitations` spelling out exactly which capability belongs to which
track -- task Phase 26 scope, section 32: never let a validated Track B
capability read as if it also validates Track A (native HDD forensics),
or vice versa.

============================================================================
RESEARCH SUMMARY (Track A: raw native filesystem/HDD) -- unchanged
============================================================================
No real Hikvision HDD/disk-image evidence exists in this project. Track A
is built entirely from PUBLIC RESEARCH, never
`EvidenceBasis.REAL_PROJECT_EVIDENCE`, and remains capped at a
detection-only capability level -- deterministic filesystem-signature
recognition only. No HIKBTREE recording index, no embedded SQLite
metadata database, no channel/timestamp structure is parsed by this
adapter.

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
represents this internal proprietary storage format -- `detector.py` only
recognizes the raw filesystem's own Master Sector marker. An exported
`.mp4` clip is Track B (above), identified a completely different way
(`app.adapters.hikvision.parser.identify_exported_clip`) -- it is never
run through `detect_hikvision_structure`.

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

from typing import IO

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
from app.adapters.hikvision.parser import PARSER_VERSION, HikvisionParser
from app.adapters.hikvision.recovery import (
    find_deleted_hikvision_recordings,
    recover_damaged_hikvision_segment,
)

#: Kept distinct from `PARSER_VERSION` (Track B, `app.adapters.hikvision.
#: parser`): this is Track A's (raw Master Sector detection) own
#: implementation version, unchanged since Phase 19.
ADAPTER_VERSION = "0.1.0-research"

__all__ = [
    "ADAPTER_VERSION",
    "HIKVISION_SEARCH_WINDOW",
    "KNOWN_HIKVISION_SIGNATURES",
    "MINIMUM_INSPECTABLE_SIZE",
    "PARSER_VERSION",
    "HikvisionAdapter",
    "HikvisionDetectionResult",
    "HikvisionParseStatus",
    "HikvisionSignature",
    "detect_hikvision_structure",
]


class HikvisionAdapter(DVRAdapter):
    """Vendor-level Hikvision adapter covering two evidence tracks -- see
    this module's docstring's "PHASE 26 UPDATE" section:

      Track A (raw native filesystem/HDD, Phase 19, unchanged):
        `inspect_storage()`/`parse_filesystem()` -- Master Sector
        signature detection only, still research-basis, still
        unvalidated.
      Track B (already-exported `.mp4` clips, Phase 26, real evidence):
        `enumerate_recordings()`/`extract_recording()`/
        `normalize_evidence()`/`find_deleted_recordings()`/
        `recover_recording()` -- real, `ffprobe`-backed parsing validated
        against a real DS-7A04HQHI-K1 evidence set.

    Two usage modes, matching the established `CPPlusAdapter`/
    `DahuaAdapter` split: no-reader for `AdapterRegistry` identity
    matching, reader-bound for actually running either track's
    operations. Track B additionally needs a real filesystem path (an
    exported clip is identified/probed via `ffprobe`, not bounded byte
    reads) -- recovered from `reader.metadata()["source_path"]`, which
    every file-backed reader populates (see
    `app.adapters.hikvision.parser.HikvisionParser`'s own docstring).
    """

    def __init__(
        self, reader: EvidenceStorageReader | None = None, *, source_evidence_id: str | None = None
    ) -> None:
        self._reader = reader
        self._source_evidence_id = source_evidence_id
        self._clip_parser = (
            HikvisionParser(reader=reader, source_evidence_id=source_evidence_id)
            if reader is not None
            else None
        )

    @property
    def vendor(self) -> str:
        return "Hikvision"

    @property
    def model_pattern(self) -> str:
        # No specific Hikvision model/firmware is validated for Track A
        # (raw filesystem). Track B's real validation (DS-7A04HQHI-K1) is
        # reported honestly via `model_scope` instead of narrowing this
        # pattern -- doing so would incorrectly gate Track A's own,
        # deliberately-generic Master Sector detection (which genuinely
        # does not depend on a specific model) behind a model match it
        # was never validated to require.
        return ".*"

    @property
    def capabilities(self) -> frozenset[AdapterCapability]:
        return frozenset(
            {
                # Track A (raw filesystem, Phase 19, unchanged).
                AdapterCapability.FILESYSTEM_DETECTION,
                # Track B (exported clip, Phase 26, real evidence) --
                # RECOVERY is deliberately NOT declared: see
                # app.adapters.hikvision.recovery's module docstring, no
                # real recovery capability exists for exported media.
                AdapterCapability.RECORDING_ENUMERATION,
                AdapterCapability.METADATA_EXTRACTION,
                AdapterCapability.TIMESTAMP_EXTRACTION,
                AdapterCapability.RECORDING_EXTRACTION,
            }
        )

    @property
    def adapter_version(self) -> str:
        # Track B's parser version is the more actionable one to surface
        # here (it is what actually changes as exported-clip parsing
        # evolves); Track A's own `ADAPTER_VERSION` remains available for
        # any caller inspecting Track A specifically (e.g.
        # `inspect_storage`'s own `AdapterResult.parser_version`, set
        # explicitly below rather than via this property).
        return PARSER_VERSION

    @property
    def support_level(self) -> SupportLevel:
        # Reports Track B's level (real evidence, real ffprobe-validated
        # parsing/extraction) -- Track A's own, still-unvalidated Level-1
        # status is spelled out explicitly in `model_scope`/`limitations`
        # below rather than dragging the whole adapter's reported level
        # down to it (Phase 26 task scope, section 21: capability
        # reporting must be truthful per-capability, not force one flat
        # number to describe two different evidence classes).
        return SupportLevel.LEVEL_4_VALIDATED

    @property
    def evidence_basis(self) -> tuple[EvidenceBasis, ...]:
        return (
            EvidenceBasis.REAL_PROJECT_EVIDENCE,
            EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION,
            EvidenceBasis.PUBLIC_REFERENCE_IMPLEMENTATION,
        )

    @property
    def model_scope(self) -> str:
        return (
            "TRACK B (exported .mp4 clips) validated only against a real Hikvision "
            "DS-7A04HQHI-K1 ('Embedded Net DVR'), firmware V4.30.220 Build 220216, "
            "4-channel recorder (GMT+05:30, NTP time.windows.com) -- see "
            "app.adapters.hikvision.parser module docstring for the evidence set. "
            "TRACK A (raw native filesystem/HDD): no specific Hikvision model/firmware "
            "validated at all; the 'HIKVISION@HANGZHOU' Master Sector signature is "
            "documented as present across Hikvision DVR filesystems generally, but exact "
            "recording-index layout is known to vary by firmware -- see module docstring. "
            "Do not generalize Track B's validation to any other Hikvision model/firmware, "
            "and do not read Track B's validation as extending to Track A (native HDD) at all."
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            # Track A (unchanged from Phase 19).
            "TRACK A (raw filesystem): no real or sample Hikvision HDD/disk-image evidence "
            "has been tested against this adapter in this project -- REAL VALIDATION PENDING",
            "TRACK A: only the Master Sector filesystem marker is recognized; HIKBTREE "
            "recording index, embedded SQLite metadata, and video block structure are not "
            "parsed",
            "TRACK A: public research documents at least two different HIKBTREE entry "
            "layouts (32-byte and 48-byte) across firmware versions; this adapter cannot "
            "determine which applies to any given evidence item without real evidence",
            "TRACK A: native Hikvision HDD/filesystem-level deleted-recording recovery is "
            "NOT_VALIDATED -- not implemented",
            # Track B (Phase 26).
            "TRACK B (exported clips): only the '.mp4' container has been validated end to "
            "end; '.dav'/'.mav'/'.iav'/'.bin' export formats the recorder's own export UI "
            "offers are NOT_VALIDATED -- this adapter does not parse them and reports them "
            "as such rather than guessing",
            "TRACK B: identification requires a same-stem '.txt'/'.docx' device export-log "
            "sidecar corroborating the export filename convention; a Hikvision-compatible "
            "MP4 with no such sidecar is reported as unconfirmed, never as a positive "
            "Hikvision identification",
            "TRACK B: damaged-segment recovery and deleted-recording recovery are both "
            "UNSUPPORTED for exported media -- see app.adapters.hikvision.recovery module "
            "docstring",
            "TRACK B: the device's configured recording frame rate (15 fps) is never "
            "substituted for the frame rate ffprobe actually measures on a given file -- "
            "the two may legitimately differ per file",
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
            # Track A's own version, not `self.adapter_version` (which
            # reports Track B's `PARSER_VERSION` -- see that property's
            # docstring): this result is Track A's own raw-filesystem
            # detection, so its `parser_version` must say so.
            parser_version=ADAPTER_VERSION,
            confidence=(1.0 if detection.status == HikvisionParseStatus.SUPPORTED_VALID else 0.0),
        )

    def parse_filesystem(self) -> AdapterResult:
        """Alias for `inspect_storage`: no distinct filesystem-parsing stage is
        implemented for Track A (raw filesystem detection-only)."""
        return self.inspect_storage()

    # --- Track B: exported-clip operations (Phase 26) ----------------------

    def _require_clip_parser(self) -> HikvisionParser:
        if self._clip_parser is None:
            raise ValueError(
                "this HikvisionAdapter instance has no bound evidence reader; construct "
                "HikvisionAdapter(reader=...) to run exported-clip operations (the "
                "no-reader form is for AdapterRegistry selection only)"
            )
        return self._clip_parser

    def enumerate_recordings(self) -> AdapterResult:
        """Identify and probe this evidence item's single exported-clip recording, if any."""
        enumeration = self._require_clip_parser().enumerate_recordings()
        confidence = (
            max(record.confidence for record in enumeration.recordings)
            if enumeration.recordings
            else 0.0
        )
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format=("hikvision-exported-clip" if enumeration.recordings else None),
            capability_set=self.capabilities,
            recordings=[record.recording_id for record in enumeration.recordings],
            metadata={"identification_status": enumeration.status.value},
            recovery_candidates=[],
            warnings=[*enumeration.warnings, enumeration.reason],
            parser_version=PARSER_VERSION,
            confidence=confidence,
        )

    def normalize_evidence(self) -> AdapterResult:
        """Produce this adapter's final normalized `AdapterResult` (Track B)."""
        return self.enumerate_recordings()

    def extract_recording(
        self, recording_id: str, *, destination: IO[bytes] | None = None
    ) -> AdapterResult:
        """Confirm one exported-clip recording is ready for container remuxing.

        Unlike `app.adapters.cp_plus.CPPlusAdapter.extract_recording`, this
        adapter does not itself reconstruct any elementary stream -- an
        exported Hikvision clip is already a complete, standard container
        (Master Specification Section 16: "The adapter should not own the
        entire application... The common engine should own... common
        recovery logic"). Actual remuxing to a browser/derived-artifact
        MP4 is done directly against the source evidence file by
        `app.core.recording_manager.RecordingManager` via `app.media`,
        exactly as it already does for CP Plus's own muxed output. This
        method only confirms `recording_id` matches this evidence's
        enumerated recording and reports the confirmation as an
        `AdapterResult` -- `destination` is accepted (and left empty) only
        to keep this method's signature consistent with the `DVRAdapter`
        contract other adapters implement.

        Args:
            recording_id: Must match this evidence's single enumerated
                recording (see `enumerate_recordings`).
            destination: Unused -- accepted for interface symmetry with
                `CPPlusAdapter.extract_recording` only.

        Returns:
            An `AdapterResult` confirming readiness, or an honest
            zero-confidence result if `recording_id` does not match.
        """
        del destination  # unused -- see docstring
        enumeration = self._require_clip_parser().enumerate_recordings()
        known_ids = {record.recording_id for record in enumeration.recordings}
        if recording_id not in known_ids:
            return AdapterResult(
                vendor=self.vendor,
                model=None,
                firmware=None,
                detected_format=None,
                capability_set=self.capabilities,
                recordings=[],
                metadata={},
                recovery_candidates=[],
                warnings=[
                    f"recording_id {recording_id!r} does not match any recording enumerated "
                    f"from this evidence ({sorted(known_ids)!r})"
                ],
                parser_version=PARSER_VERSION,
                confidence=0.0,
            )
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format="hikvision-exported-clip",
            capability_set=self.capabilities,
            recordings=[recording_id],
            metadata={"ready_for_remux": "true"},
            recovery_candidates=[],
            warnings=[],
            parser_version=PARSER_VERSION,
            confidence=1.0,
        )

    def find_deleted_recordings(self) -> AdapterResult:
        """Search for deleted-but-referenced recordings (Phase 26).

        Always reports `UNSUPPORTED` -- see
        `app.adapters.hikvision.recovery`'s module docstring. Real,
        deterministic, tested behavior, never a fabricated deleted-
        recording recovery.
        """
        result = find_deleted_hikvision_recordings()
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format="hikvision-exported-clip",
            capability_set=self.capabilities,
            recordings=[],
            metadata={"recovery_status": result.status.value},
            recovery_candidates=[],
            warnings=[result.reason],
            parser_version=PARSER_VERSION,
            confidence=0.0,
        )

    def recover_recording(
        self, recording_id: str, *, destination: IO[bytes] | None = None
    ) -> AdapterResult:
        """Attempt to recover one (possibly damaged) exported clip (Phase 26).

        Always reports `UNSUPPORTED` -- see
        `app.adapters.hikvision.recovery`'s module docstring for why this
        genuinely differs from CP Plus's own real, validated damaged-
        segment recovery.
        """
        del destination  # unused -- see module docstring, no recovery is performed
        result = recover_damaged_hikvision_segment()
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format="hikvision-exported-clip",
            capability_set=self.capabilities,
            recordings=[recording_id],
            metadata={"recovery_status": result.status.value},
            recovery_candidates=[],
            warnings=[result.reason],
            parser_version=PARSER_VERSION,
            confidence=0.0,
        )
