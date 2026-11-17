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
# THE "IMKH" MARKER IS HIKVISION'S OWN FILE HEADER, AND IS THE PRIMARY
# IDENTIFICATION SIGNAL (corrected in the Phase 26 repair -- the first
# delivery wrongly dismissed it and depended on filename + sidecar instead,
# neither of which the real single-file upload path can supply):
#
#   - The 4 bytes `49 4D 4B 48` read little-endian are 0x484B4D49, the ASCII
#     tag "HKMI" -- the `media_fourcc` of Hikvision's public SDK structure
#     `HIK_MEDIAINFO` (`plaympeg4.h`, PlayCtrl SDK; a web search attributes
#     exactly this struct and value to that header -- the header text itself
#     could not be fetched, so no constant *names* are asserted from it).
#   - Decoding the 24-byte header as that struct (little-endian:
#     fourcc, version, device_id, system_format, video_format,
#     audio_format, audio_channels, audio_bits, audio_sample_rate,
#     audio_bitrate) yields, for ALL THREE real files,
#     system_format=2, video_format=5, audio_format=0x7110, channels=1,
#     sample_rate=8000 -- which agree field-for-field with ffprobe's
#     INDEPENDENT reading of the payload (MPEG-PS, hevc, pcm_mulaw, mono,
#     8000 Hz). A coincidental byte pattern would not decode into values
#     that all match an independent decoder. Only these observed
#     code<->codec pairings are asserted (`OBSERVED_HEADER_CODE_MEANINGS`);
#     any other code is reported raw, never guessed.
#   - The remaining 232 bytes of the 256-byte header region are zero: the
#     header carries NO timestamp and NO device id/model/serial. Those must
#     come from elsewhere (original filename; export-log sidecar).
#   - The MPEG-PS private-stream (0xBD) payloads that follow are not
#     readable text (they look scrambled); no wall-clock time is
#     recoverable from them by this project.
#
# Header-only identification therefore confirms "Hikvision-format export"
# (vendor) at 0.9 confidence, and NEVER a model/serial/firmware. A
# same-stem export-log sidecar, when present, upgrades it to 1.0 and is the
# only source of the serial (-> `KNOWN_HIKVISION_DEVICES`).
# ============================================================================


# ============================================================================
# PHASE 26 -- EXPORTED CLIP EVIDENCE MODEL
# ============================================================================
# Everything below is the second, real-evidence-backed track described in
# this module's own docstring above: an already-exported Hikvision `.mp4`
# clip (a standard PS container, not the raw proprietary filesystem
# `HikvisionDetectionResult` above answers for). See
# `app.adapters.hikvision.parser`'s module docstring for how it is identified
# and `HikvisionClipIdentificationStatus` for the honesty levels.

#: Hikvision `HIK_MEDIAINFO.media_fourcc` ("HKMI") as it appears on disk
#: (little-endian dword 0x484B4D49).
HIKVISION_MEDIA_HEADER_MAGIC = b"IMKH"

#: `struct` format of the leading 24 bytes of the header (little-endian).
HIKVISION_MEDIA_HEADER_STRUCT = "<IHHHHHBBII"
HIKVISION_MEDIA_HEADER_SIZE = 24

#: Standard MPEG-2 Program Stream pack-header start code (ISO/IEC 13818-1).
MPEG_PS_PACK_START_CODE = b"\x00\x00\x01\xba"

#: How far past offset 0 the PS payload's start code is searched for. Bounded
#: (never "read until found"); the observed padding is 4532-7204 bytes.
HIKVISION_PS_SEARCH_WINDOW = 65536

#: Header code -> what ffprobe independently reported on the real evidence.
#: ONLY pairings actually observed and cross-validated are listed; any other
#: code is reported raw and never mapped.
OBSERVED_HEADER_CODE_MEANINGS: dict[str, dict[int, str]] = {
    "system_format": {0x0002: "mpeg"},  # ffprobe format_name: MPEG-PS
    "video_format": {0x0005: "hevc"},  # ffprobe video codec_name
    "audio_format": {0x7110: "pcm_mulaw"},  # ffprobe audio codec_name
}


@dataclass(frozen=True)
class HikvisionMediaHeader:
    """The decoded 24-byte Hikvision `HIK_MEDIAINFO`-style file header (see the
    module-level comment above for the evidence basis of each field)."""

    version: int
    device_id: int
    system_format: int
    video_format: int
    audio_format: int
    audio_channels: int
    audio_bits_per_sample: int
    audio_sample_rate: int
    audio_bitrate_field: int
    #: Offset of the first MPEG-PS pack start code (00 00 01 BA), or `None` if
    #: none was found within `HIKVISION_PS_SEARCH_WINDOW`.
    ps_payload_offset: int | None


class HikvisionClipIdentificationStatus(str, Enum):
    """Outcome of identifying whether an exported `.mp4` file is genuinely
    Hikvision evidence, as opposed to a generic H.265/H.264 media file
    that merely happens to look compatible (task Phase 26 scope, section 7).
    """

    #: A same-stem export-log sidecar (`.txt`/`.docx`) was found next to the
    #: clip, carries the Hikvision copyright banner, and the filename matches
    #: the export naming convention. Confidence 1.0. The only status that can
    #: yield a serial number -> known-device model/firmware.
    CONFIRMED_BY_EXPORT_LOG = "confirmed_by_export_log"
    #: The file itself begins with Hikvision's own media header ("IMKH") and
    #: wraps an MPEG-PS payload -- no sidecar needed. Confidence 0.9 (0.5 if a
    #: decoded header field disagrees with ffprobe). Vendor only: never a
    #: model, serial or firmware.
    CONFIRMED_BY_CONTAINER_HEADER = "confirmed_by_container_header"
    #: Only the filename matches the naming convention -- NOT treated as
    #: Hikvision-confirmed (never claim a vendor from a filename alone).
    FILENAME_PATTERN_ONLY = "filename_pattern_only"
    #: No Hikvision-specific signal at all.
    UNSUPPORTED = "unsupported"

    @property
    def is_confirmed(self) -> bool:
        return self in (
            HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG,
            HikvisionClipIdentificationStatus.CONFIRMED_BY_CONTAINER_HEADER,
        )


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
    #: The device's own configured time zone label, as displayed on its
    #: System Settings screen.
    timezone: str
    #: IANA zone the normalization engine can resolve (`app.timeline.timezone`
    #: only accepts IANA names) that is equivalent to `timezone` for this
    #: device: the screen reads "(GMT+05:30) Madras, Bombay, ..." with DST
    #: disabled, i.e. a fixed +05:30 -- India's `Asia/Kolkata` has no DST.
    iana_timezone: str
    #: Provenance carried into `timestamp_source_timezone_basis`.
    timezone_basis: str


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
        iana_timezone="Asia/Kolkata",
        timezone_basis=(
            "recorder System Settings screen: Time Zone '(GMT+05:30) Madras, Bombay...', "
            "DST disabled (examiner-photographed alongside the evidence set). NTP is enabled "
            "(time.windows.com, 30 min) but that does not verify any individual timestamp."
        ),
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
    #: The decoded file header, when the file begins with Hikvision's "IMKH"
    #: media header (independent of whether a sidecar also exists).
    media_header: HikvisionMediaHeader | None = None


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
    #: What the SOURCE file's own ffprobe pass reported, preserved verbatim
    #: alongside the (possibly different) `fps`/`container` above, which are
    #: what the recording row carries. For the real evidence the container
    #: DECLARES avg 30 / r 25 fps but the packet count proves ~15 fps.
    source_container: str | None = None
    declared_avg_frame_rate: float | None = None
    declared_r_frame_rate: float | None = None
    video_packet_count: int | None = None
    measured_fps: float | None = None
    #: Human-readable per-field agreement between the decoded Hikvision header
    #: and ffprobe (only for pairings observed on real evidence).
    header_probe_consistency: str | None = None


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
