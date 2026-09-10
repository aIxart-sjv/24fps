"""
Hikvision adapter data model (Phase 19, "Additional OEM Adapters").
Master Specification Section 17 ("Target OEM Adapters" names HIKVISION /
Hikvision).

RESEARCH-EVIDENCE STATUS (raw Master-Sector/HDD detection, below)
------------------------------------------------------------------
Everything in THIS section of the module (`HikvisionParseStatus`,
`HikvisionSignature`, `KNOWN_HIKVISION_SIGNATURES`,
`HikvisionDetectionResult`) is still built from PUBLIC RESEARCH --
`EvidenceBasis.PUBLIC_FORMAT_DOCUMENTATION` (a peer-reviewed academic
paper) and `EvidenceBasis.PUBLIC_REFERENCE_IMPLEMENTATION` (an inspected,
MIT-licensed open-source parser) -- never `EvidenceBasis.
REAL_PROJECT_EVIDENCE`. It answers only "does this evidence contain the
raw Hikvision filesystem's own Master Sector marker" (native HDD/disk
image territory) and remains unvalidated against any real evidence.

Phase 26 added a SECOND, separate, real-evidence-backed section further
down this module (`HikvisionClipFilenameInfo` onward) for a different
evidence class entirely: already-exported Hikvision `.mp4` clips (a
standard container the device's own export feature produces), validated
against a real Hikvision DS-7A04HQHI-K1 (firmware V4.30.220 Build 220216)
evidence set -- see `app.adapters.hikvision.parser`'s module docstring for
that section's own evidence basis. The two sections answer genuinely
different questions (raw proprietary filesystem vs. already-exported
standard container) and must not be conflated -- see
`app.adapters.hikvision`'s module docstring for how `HikvisionAdapter`
reports both.

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

from dataclasses import dataclass, field
from datetime import datetime
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


# ============================================================================
# Phase 26 -- Hikvision EXPORTED-MEDIA pathway ("native export" acquisition,
# Master Specification Section 9 Path 1), layered on top of (never
# replacing) the Phase 19 raw-filesystem detection above.
#
# EVIDENCE BASIS: real, controlled Hikvision evidence --
# `~/Documents/24fps-evidence/Hikvision/` -- three exported clips
# (A01_20260829100000.mp4, A01_20260831080000.mp4, A02_20260831080000.mp4)
# plus their device export-log sidecars, from a confirmed device (see
# `app.adapters.hikvision`'s module docstring for the full device fact
# sheet: model DS-7A04HQHI-K1, firmware V4.30.220 Build 220216). This is
# `EvidenceBasis.REAL_PROJECT_EVIDENCE` -- the first time this adapter can
# honestly claim it, distinct from the Phase 19 filesystem-detection
# pathway above, which remains `PUBLIC_FORMAT_DOCUMENTATION`/
# `PUBLIC_REFERENCE_IMPLEMENTATION` only.
#
# WHAT THE REAL EVIDENCE ACTUALLY IS: despite the `.mp4` extension, none of
# the three files is a standard ISOBMFF MP4 (no `ftyp`/`moov` box at offset
# 0). Byte-level inspection of all three real files found a raw MPEG-2
# Program Stream carrying one HEVC video elementary stream and one G.711
# mu-law (PCM) audio elementary stream, preceded by a fixed 4-byte ASCII
# "IMKH" marker (0x494D4B48) and a file-dependent zero-padded header
# region. `ffprobe`/`ffmpeg` (no special flags) already auto-detect and
# skip past that header on their own probing heuristic and correctly demux
# the underlying MPEG-PS -- confirmed against all three real files (see
# `app.media.decoder`).
#
# THIS "IMKH" MARKER IS DELIBERATELY *NOT* USED FOR VENDOR IDENTIFICATION:
# nothing in this project's public research or reference sources documents
# "IMKH" as a Hikvision-specific signature (unlike Phase 19's
# "HIKVISION@HANGZHOU", which two independent sources corroborate). It may
# be a generic export-muxer artifact shared by other tools/vendors --
# treating it as proof of Hikvision origin would be exactly the "invent
# field semantics from coincidental byte patterns" failure mode this
# project's task scope explicitly forbids. This adapter instead identifies
# an exported clip the way an examiner actually would: by cross-checking
# the export filename convention against the device's own generated
# export-log sidecar (`app.adapters.hikvision.parser.identify_exported_clip`)
# -- see that module's docstring for the full mechanism and honesty levels
# (`HikvisionClipIdentificationStatus`).
# ============================================================================


# ============================================================================
# PHASE 26 -- EXPORTED CLIP EVIDENCE MODEL
# ============================================================================
# Everything below is the second, real-evidence-backed track described in
# this module's own docstring above: an already-exported Hikvision `.mp4`
# clip (a standard container, not the raw proprietary filesystem
# `HikvisionDetectionResult` above answers for), identified via the
# device's own export-log sidecar file rather than any in-container magic
# byte -- see `app.adapters.hikvision.parser`'s module docstring for why
# no in-container Hikvision signature exists to check for a plain H.265/
# MPEG-PS stream, and full evidence-basis citations for every field below.


class HikvisionClipIdentificationStatus(str, Enum):
    """Outcome of identifying whether an exported `.mp4` file is genuinely
    Hikvision evidence, as opposed to a generic H.265/H.264 media file
    that merely happens to look compatible.

    Deliberately does not mirror `HikvisionParseStatus`
    (`SUPPORTED_VALID`/`UNSUPPORTED`/`UNKNOWN`): this is a *sidecar-log*
    identification, not a structural container match, so the vocabulary
    names that explicitly (task Phase 26 scope, section 7: "distinguish
    between evidence that is actually associated with a confirmed
    Hikvision device" and "a generic media file that merely looks
    compatible").
    """

    #: The filename matched the documented Hikvision channel-export naming
    #: convention AND a sidecar export-log (`.txt`/`.docx`) was found,
    #: read, and its own content corroborates this specific file (matching
    #: device serial number, Hikvision copyright banner, an "made video
    #: export" statement). The strongest identification this adapter can
    #: make without a native filesystem/HDD acquisition.
    CONFIRMED_BY_EXPORT_LOG = "confirmed_by_export_log"
    #: The filename matches the naming convention, but no sidecar log could
    #: be found/read/parsed to corroborate it -- this is NOT treated as
    #: Hikvision-confirmed (task Phase 26 scope: never claim a recorder
    #: model from generic H.265 metadata alone).
    FILENAME_PATTERN_ONLY = "filename_pattern_only"
    #: Neither the filename nor any sidecar log gives a Hikvision-specific
    #: signal.
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class HikvisionExportLogSidecar:
    """Parsed content of one Hikvision device export-log sidecar file
    (`.txt` or `.docx`, same base name as the exported clip -- e.g.
    `A01_20260829100000.txt` alongside `A01_20260829100000.mp4`).

    Evidence basis: this is the DVR's own generated export receipt, not
    this project's inference -- every field here is read verbatim from
    that file's own text (Phase 26 real evidence set,
    `~/Documents/24fps-evidence/Hikvision/`). Never fabricated when a
    field's expected line is not found -- stays `None` instead.
    """

    source_path: str
    is_hikvision_copyright_banner_present: bool
    device_serial: str | None
    export_user: str | None
    export_timestamp: datetime | None
    log_entry_count: int | None
    raw_text: str


class HikvisionClipTimestampSource(str, Enum):
    """Where an exported clip's `start_original` was actually derived
    from -- mirrors `app.adapters.cp_plus.models`' own filename-vs-binary
    distinction (never conflate the two)."""

    #: Parsed from the export filename's own `<channel>_<YYYYMMDDHHMMSS>`
    #: convention (Phase 26 real evidence: `A01_20260829100000.mp4`) --
    #: this is the recording's own start time as the device/export tool
    #: labeled it, not the (separate, later) export action time recorded
    #: in the sidecar log.
    FILENAME_DERIVED = "filename_derived"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HikvisionKnownDevice:
    """One specific, examiner-confirmed Hikvision device this project has
    actually validated -- model/firmware are asserted only for a device
    serial number this project independently confirmed against that
    device's own on-screen system-information display (photographed
    alongside the real evidence set, `~/Documents/24fps-evidence/
    Hikvision/`), never inferred from the serial number's own structure
    or from generic evidence (task Phase 26 scope, section 7: distinguish
    a confirmed device from "a generic media file that merely looks
    compatible")."""

    serial_number: str
    device_name: str
    model: str
    firmware: str
    channels: int
    timezone: str


#: The one Hikvision device this project has examiner-confirmed end to
#: end: physically inspected (device information + network/time screens
#: photographed) and cross-checked against every real exported clip's
#: sidecar export-log serial number. Extending this table to a new serial
#: requires the same kind of direct confirmation -- never adding an entry
#: from a plausible-looking or partially-matching serial.
KNOWN_HIKVISION_DEVICES: dict[str, HikvisionKnownDevice] = {
    "0420220517CCWRJ98043179WCVU": HikvisionKnownDevice(
        serial_number="0420220517CCWRJ98043179WCVU",
        device_name="Embedded Net DVR",
        model="DS-7A04HQHI-K1",
        firmware="V4.30.220, Build 220216",
        channels=4,
        timezone="GMT+05:30",
    ),
}


def lookup_known_hikvision_device(serial_number: str) -> HikvisionKnownDevice | None:
    """Look up `serial_number` in `KNOWN_HIKVISION_DEVICES`.

    Returns:
        The matching `HikvisionKnownDevice`, or `None` if this serial has
        not been examiner-confirmed by this project -- never a guessed or
        partial match.
    """
    return KNOWN_HIKVISION_DEVICES.get(serial_number)


@dataclass(frozen=True)
class HikvisionClipFilenameInfo:
    """Best-effort information parsed from a Hikvision export filename
    (`<channel>_<YYYYMMDDHHMMSS>.mp4`, e.g. `A01_20260829100000.mp4`).

    `channel_label` preserves the export tool's own channel naming
    verbatim (e.g. `"A01"`); `channel_number` is the trailing integer
    parsed from it (e.g. `1`) when present -- both are kept since
    `Recording.camera_id` (str) and `Recording.channel` (int) are
    separate columns.
    """

    channel_label: str | None
    channel_number: int | None
    start_original: datetime | None


@dataclass(frozen=True)
class HikvisionClipIdentificationResult:
    """Result of identifying whether one evidence file is a genuine
    Hikvision-exported clip (`app.adapters.hikvision.parser.
    identify_exported_clip`).

    `known_device` is populated only when `sidecar.device_serial` matches
    `KNOWN_HIKVISION_DEVICES` -- i.e. only for this project's one
    examiner-confirmed device. A `CONFIRMED_BY_EXPORT_LOG` identification
    with `known_device is None` still means a genuine Hikvision device
    (the sidecar's own copyright banner + export statement confirm that),
    just not this project's specific confirmed one -- model/firmware must
    not be inferred for it.
    """

    status: HikvisionClipIdentificationStatus
    filename_info: HikvisionClipFilenameInfo | None
    sidecar: HikvisionExportLogSidecar | None
    reason: str
    warnings: list[str] = field(default_factory=list)
    known_device: HikvisionKnownDevice | None = None


@dataclass(frozen=True)
class HikvisionRecordingRecord:
    """One recording discovered from a Hikvision exported clip.

    Fields mirror `app.models.recording.Recording`'s normalized columns
    (Master Specification Section 6, "Normalized Evidence Model") --
    same shape/intent as `app.adapters.cp_plus.models.
    CPPlusRecordingRecord`, see `to_recording_fields` below. Unlike CP
    Plus's proprietary container (which carries no codec/resolution/fps
    of its own), an exported Hikvision clip is a standard, ffprobe-
    readable container -- so `codec`/`container`/`width`/`height`/`fps`/
    `duration_ms`/`has_audio` here are real, ffprobe-measured values from
    a read-only pass over the *source* evidence file itself, not a later
    derived artifact (Phase 26 task scope, section 9: "must be tested
    through the real 24FPS pipeline"; the device's own configured 15 fps
    is never substituted for whatever `fps` ffprobe actually measured --
    task scope section 19: "Do NOT hardcode 25 FPS[/any fixed value]").
    """

    recording_id: str
    camera_id: str | None
    channel: int | None
    start_original: datetime | None
    end_original: datetime | None
    duration_ms: int | None
    codec: str | None
    container: str | None
    width: int | None
    height: int | None
    fps: float | None
    has_audio: bool | None
    audio_codec: str | None
    source_evidence_id: str | None
    identification: HikvisionClipIdentificationResult
    parser_version: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    timestamp_source: HikvisionClipTimestampSource = HikvisionClipTimestampSource.UNKNOWN


@dataclass(frozen=True)
class HikvisionEnumerationResult:
    """Result of enumerating recordings from a Hikvision exported-clip evidence source."""

    status: HikvisionClipIdentificationStatus
    recordings: list[HikvisionRecordingRecord]
    warnings: list[str]
    parser_version: str
    reason: str


def to_recording_fields(record: HikvisionRecordingRecord) -> dict[str, object]:
    """Map one `HikvisionRecordingRecord` onto `app.models.recording.
    Recording`'s field names -- mirrors `app.adapters.cp_plus.models.
    to_recording_fields` exactly in intent (Master Specification Section 9,
    "Normalized Output"), returning plain constructor kwargs so this module
    never needs to import SQLAlchemy.

    Unlike CP Plus's own mapping (which always maps codec/container/width/
    height/fps/duration_ms to `None` -- its container carries none of
    them), every one of those fields here carries the real value ffprobe
    measured from the source evidence file, since an exported Hikvision
    clip is a standard container Phase 26 validated end-to-end.

    Args:
        record: The recording to map.

    Returns:
        A dict whose keys are exactly the mutable, non-identity column
        names on `Recording`.
    """
    return {
        "recording_id": record.recording_id,
        "camera_id": record.camera_id,
        "channel": record.channel,
        "start_original": record.start_original,
        "end_original": record.end_original,
        "start_normalized": None,
        "end_normalized": None,
        "duration_ms": record.duration_ms,
        "codec": record.codec,
        "container": record.container,
        "width": record.width,
        "height": record.height,
        "fps": record.fps,
        "source_location": f"hikvision_exported_clip:{record.source_evidence_id}",
        "recovery_status": None,
        "recovery_method": None,
        "confidence": record.confidence,
        "artifact_id": None,
    }
