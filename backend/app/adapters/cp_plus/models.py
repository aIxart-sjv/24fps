"""
CP Plus adapter data model (Phase 8 / Fourth Backend Milestone).
Master Specification Section 93 ("Fourth Backend Milestone") and the Phase 8
task scope, sections 3-5 and 10 ("Parser Contract", "Recording Enumeration",
"Metadata Extraction", "Error Handling").

CONTROLLED-EVIDENCE STATUS
---------------------------
`KNOWN_CP_PLUS_SIGNATURES` now holds one real, validated signature (label
`"ADIT-v1"`). It was derived from a read-only, byte-level comparative
analysis of 13 real CP Plus `.cpv` export files plus `CPV Player.exe`,
supplied as a controlled evidence package at
`~/Documents/24fps-evidence/cp-plus-2026-08-28/` (SHA-256/MD5 verified
against the package's own manifests before and after analysis). The full
analysis — byte-level tables, confidence levels, and everything that
remains unresolved — is recorded in that package's
`analysis/CPV_ANALYSIS_REPORT.md`; this module and `container.py`
implement only what that report established with direct evidence.

Known device this evidence came from (do not generalize beyond it — Master
Specification Section 17: "Never report 'CP Plus fully supported' if only
one model is tested"):

    Vendor:   CP Plus
    NVR:      CP-UNR-108F1, hardware V1.0, firmware V1.00.14.01.R
    Camera:   CP-UNC-TA21L3C-LQ (CH1, 1920x1080, H.265, continuous)

This signature and the record-framing logic in `container.py` are
validated **only** against that one NVR/firmware/camera combination. Any
other CP Plus model, firmware, or export tool may use a different
container layout entirely; nothing here should be read as "CP Plus
support" in general.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# --- Container structural constants ---
# Evidence basis: verified with zero footer mismatches across a full,
# length-jump walk of all 13 real evidence files (tens of thousands of
# records) — see CPV_ANALYSIS_REPORT.md and this module's docstring.

#: Size in bytes of the outer "ADIT" file header preceding the first record.
OUTER_HEADER_SIZE = 1024

#: Size in bytes of one record's fixed header: magic(4) + type_tag(4) +
#: counter(4) + length(4).
RECORD_HEADER_SIZE = 16

#: Size in bytes of one record's fixed footer: lowercase magic(4) +
#: length-repeat(4).
RECORD_FOOTER_SIZE = 8

#: The smallest possible well-formed record: header + footer, zero-length body.
MIN_RECORD_SIZE = RECORD_HEADER_SIZE + RECORD_FOOTER_SIZE

#: Uppercase record-open magic.
RECORD_MAGIC = b"CPAV"

#: Lowercase record-close magic.
RECORD_FOOTER_MAGIC = b"cpav"

#: The 8-byte outer-header magic ("ADIT-v1" signature) — see
#: `KNOWN_CP_PLUS_SIGNATURES` below for its full validated signature entry.
ADIT_MAGIC = b"ADIT\x00\x22\x00\x00"


class CPPlusParseStatus(str, Enum):
    """Outcome of a CP Plus detection/parse operation.

    Phase 8 task scope, section 10 ("Error Handling"): the five states a
    CP Plus parser result must be able to distinguish.
    """

    SUPPORTED_VALID = "supported_valid"
    SUPPORTED_CORRUPTED = "supported_corrupted"
    SUPPORTED_PARTIAL = "supported_partial"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class CPPlusSignature:
    """One documented, validated CP Plus structural signature.

    Every field here must be backed by inspection of a real, controlled CP
    Plus fixture — never inferred from generic/internet examples or a
    plausible-looking guess (Phase 8 task scope, section 2).
    """

    label: str
    header_offset: int
    magic: bytes
    minimum_container_size: int


# "ADIT-v1": the 8-byte file magic found byte-identical at offset 0 of all
# 13 real evidence files (see CPV_ANALYSIS_REPORT.md section 3). The
# minimum container size is the outer header size — a file smaller than
# that cannot hold a complete outer header, so it cannot be this format
# regardless of its first 8 bytes.
KNOWN_CP_PLUS_SIGNATURES: tuple[CPPlusSignature, ...] = (
    CPPlusSignature(
        label="ADIT-v1",
        header_offset=0,
        magic=ADIT_MAGIC,
        minimum_container_size=OUTER_HEADER_SIZE,
    ),
)


@dataclass(frozen=True)
class CPPlusDetectionResult:
    """Answer to "does this evidence match a CP Plus structure this adapter understands?"."""

    status: CPPlusParseStatus
    matched_signature: str | None
    reason: str
    warnings: list[str] = field(default_factory=list)
    evidence_size: int = 0
    bytes_inspected: int = 0


class CPVRecordFamily(str, Enum):
    """Coarse classification of a CPV record, by the low byte of its type tag.

    Evidence basis: across a full walk of all 13 real evidence files, every
    observed `type_tag` value shares one of four low-byte values. The full
    tag (e.g. `0x0f1`, `0x6f1`, `0x9f1`, `0x19f1` — all low-byte `0xf1`) is
    preserved verbatim on `CPVRecord.type_tag`; the higher bits' meaning is
    NOT established, so it is never discarded, only classified at this
    coarse, evidence-supported granularity.

    Per-family notes (see CPV_ANALYSIS_REPORT.md and this package's
    implementation-time re-verification):
      - VIDEO_FRAME (low byte 0xFC): variable length; carries H.265 slice
        data. The dominant, size-varying record type.
      - VIDEO_FIXED_AUXILIARY (low byte 0xF0): fixed length (368 bytes in
        every sampled file, all 13 files). Purpose not established.
      - KEYFRAME_MARKER (low byte 0xFD): recurs periodically; the first
        occurrence in a file carries full VPS/SPS/PPS parameter sets.
        Later occurrences were found to carry ordinary slice data, not a
        repeated parameter set — this family name is retained only because
        it is this format's evidence-observed first-record role.
      - TELEMETRY (low byte 0xF1, any high-bit variant): carries a
        structured payload; some variants are plain JSON, others are
        binary and not decoded here.
    """

    VIDEO_FRAME = "video_frame"
    VIDEO_FIXED_AUXILIARY = "video_fixed_auxiliary"
    KEYFRAME_MARKER = "keyframe_marker"
    TELEMETRY = "telemetry"
    UNKNOWN = "unknown"


_FAMILY_BY_LOW_BYTE: dict[int, CPVRecordFamily] = {
    0xFC: CPVRecordFamily.VIDEO_FRAME,
    0xF0: CPVRecordFamily.VIDEO_FIXED_AUXILIARY,
    0xFD: CPVRecordFamily.KEYFRAME_MARKER,
    0xF1: CPVRecordFamily.TELEMETRY,
}


def classify_record_family(type_tag: int) -> CPVRecordFamily:
    """Classify a record's `type_tag` by its low byte.

    Args:
        type_tag: The raw little-endian 32-bit type tag read from a
            record's header.

    Returns:
        The matching `CPVRecordFamily`, or `CPVRecordFamily.UNKNOWN` if the
        low byte was never observed in the analyzed evidence.
    """
    return _FAMILY_BY_LOW_BYTE.get(type_tag & 0xFF, CPVRecordFamily.UNKNOWN)


class CPVRecordValidity(str, Enum):
    """Why a `CPVRecord` was (or was not) accepted as well-formed.

    `TRAILING_PADDING` is distinct from `BAD_MAGIC`: it fires only when the
    four bytes at a would-be record's offset are `0xFF 0xFF 0xFF 0xFF`,
    matching the fixed-block `0xFF` padding observed at the end of several
    real evidence files (CPV_ANALYSIS_REPORT.md section 13) — an expected
    end-of-real-records condition, not corruption. Any other mismatched
    magic is `BAD_MAGIC`, a genuine corruption signal.
    """

    VALID = "valid"
    TRUNCATED_HEADER = "truncated_header"
    BAD_MAGIC = "bad_magic"
    TRAILING_PADDING = "trailing_padding"
    INVALID_LENGTH = "invalid_length"
    LENGTH_EXCEEDS_CONTAINER = "length_exceeds_container"
    FOOTER_MISMATCH = "footer_mismatch"


class CPVTimestampStatus(str, Enum):
    """Status of a raw, not-yet-semantically-resolved CPV timestamp-like field.

    CPV_ANALYSIS_REPORT.md section 6: the outer-header counter decodes to a
    date that does not match this evidence's known real-world recording
    date. This status exists specifically so no code path can silently
    promote that counter into a trusted, real-world timestamp.
    """

    RAW_COUNTER_UNVALIDATED = "raw_counter_unvalidated"
    NOT_PRESENT = "not_present"


class CPVSessionLinkStatus(str, Enum):
    """Relationship between two adjacent CPV segments' internal counters.

    CONTINUOUS: the next segment's start counter equals the previous
        segment's end counter — exactly what all 12 adjacent pairs in the
        analyzed evidence showed.
    MISSING_SEGMENT: the next segment's start counter is *greater* than the
        previous segment's end counter — a counter range between the two
        segments is not covered by any supplied segment.
    DISCONTINUITY: the next segment's start counter is *less* than the
        previous segment's end counter (overlap / out-of-order / reset).
    DUPLICATE: two segments report an identical (start, end) counter pair.
    UNKNOWN: one or both segments' counters could not be read.
    """

    CONTINUOUS = "continuous"
    MISSING_SEGMENT = "missing_segment"
    DISCONTINUITY = "discontinuity"
    DUPLICATE = "duplicate"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CPVOuterHeader:
    """Parsed form of the 1024-byte outer "ADIT" header at offset 0.

    `reserved_all_zero` is a literal all-zero check of bytes 16-1023 — it
    is `False` on every real evidence file, because byte offset 32 is
    `0x01` (constant across all 13 real files; meaning not established).
    This was corrected during implementation from the read-only analysis
    pass's less precise "all zero" characterization, which only inspected
    short constant-byte runs individually and did not check this specific
    1008-byte region byte-for-byte.
    """

    magic_valid: bool
    version_field: bytes
    start_counter: int | None
    end_counter: int | None
    reserved_all_zero: bool | None
    bytes_read: int


@dataclass(frozen=True)
class CPVNalUnitInfo:
    """One HEVC (H.265) Annex-B NAL unit found in a record's body.

    `nal_unit_type` follows the H.265 NAL header bit layout
    (`(first_byte >> 1) & 0x3F`), decoded directly from the bytes — not
    inferred from context.
    """

    offset_in_body: int
    nal_unit_type: int
    nal_unit_name: str


_HEVC_NAL_NAMES: dict[int, str] = {
    0: "TRAIL_N",
    1: "TRAIL_R",
    19: "IDR_W_RADL",
    20: "IDR_N_LP",
    21: "CRA_NUT",
    32: "VPS",
    33: "SPS",
    34: "PPS",
    35: "AUD",
    39: "PREFIX_SEI",
    40: "SUFFIX_SEI",
}


def hevc_nal_unit_name(nal_unit_type: int) -> str:
    """Return the standard HEVC name for `nal_unit_type`, or a generic label.

    Only names present in `_HEVC_NAL_NAMES` are asserted with confidence;
    anything else is returned as an explicit, unclassified label rather
    than guessed.
    """
    return _HEVC_NAL_NAMES.get(nal_unit_type, f"type_{nal_unit_type}_unclassified")


@dataclass(frozen=True)
class CPVTelemetryPayload:
    """One TELEMETRY-family record's decoded (or decode-attempted) payload."""

    record_offset: int
    type_tag: int
    raw_text: str
    valid_json: bool
    parsed: dict[str, Any] | None


@dataclass(frozen=True)
class CPVRecord:
    """One parsed CPV record (header + optional body + footer)."""

    offset: int
    type_tag: int
    family: CPVRecordFamily
    counter: int | None
    length: int | None
    record_timestamp: int | None
    validity: CPVRecordValidity
    footer_valid: bool | None
    payload_offset: int
    payload_length: int
    warnings: tuple[str, ...] = ()

    @property
    def next_offset(self) -> int | None:
        """Offset of the next record, if this one's length was well-formed."""
        if self.length is None:
            return None
        return self.offset + self.length


@dataclass(frozen=True)
class CPVFileAnalysis:
    """Structural summary of one CPV file's record sequence.

    Produced by a single bounded/streaming walk (see `container.py`):
    every record's header and footer are read (cheap, fixed-size reads),
    while record *bodies* are only read for a bounded subset (the first
    keyframe-marker record, for NAL/parameter-set detection, and up to
    `TELEMETRY_SAMPLE_LIMIT` telemetry records) — never for the whole file.
    """

    outer_header: CPVOuterHeader | None
    record_count: int
    family_histogram: dict[CPVRecordFamily, int]
    telemetry_samples: tuple[CPVTelemetryPayload, ...]
    nal_units: tuple[CPVNalUnitInfo, ...]
    truncated: bool
    corrupted: bool
    bytes_scanned: int
    container_size: int
    last_valid_record_end: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CPVFilenameInfo:
    """Best-effort information parsed from a CP Plus export filename.

    This is explicitly filename-derived provenance (the export tool's own
    labeling), never binary-derived — kept distinct from
    `CPVOuterHeader`'s counters, which are unresolved (see
    `CPVTimestampStatus`). `None` on any field the filename did not
    actually encode; nothing here is guessed from a partial match.
    """

    channel: int | None
    stream_label: str | None
    start_original: datetime | None
    end_original: datetime | None


@dataclass(frozen=True)
class CPVSegmentDescriptor:
    """One CPV file's identity, as used for multi-file session linking."""

    label: str
    start_counter: int | None
    end_counter: int | None
    readable: bool


@dataclass(frozen=True)
class CPVSegmentLink:
    """The relationship found between two adjacent `CPVSegmentDescriptor`s."""

    previous_label: str
    next_label: str
    status: CPVSessionLinkStatus
    detail: str


@dataclass(frozen=True)
class CPVSessionLinkResult:
    """Result of linking an ordered sequence of CPV segments into one session."""

    segments: tuple[CPVSegmentDescriptor, ...]
    links: tuple[CPVSegmentLink, ...]
    overall_status: CPVSessionLinkStatus
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CPPlusRecordingRecord:
    """One recording discovered by the CP Plus parser.

    Fields mirror `app.models.recording.Recording`'s normalized columns
    (Master Specification Section 6, "Normalized Evidence Model") rather
    than introducing a CP Plus-only shape — see `to_recording_fields`
    below. Every field the source evidence does not actually provide stays
    `None`; nothing here is ever guessed (Section 6: "If a value cannot be
    reliably determined, record an explicit unavailable state.").

    `start_original`/`end_original` are populated only from a parsed export
    filename (`CPVFilenameInfo`), when available — never from the
    unresolved binary counter, which is instead preserved verbatim via
    `raw_timestamp`/`timestamp_source`/`timestamp_interpretation`/
    `timestamp_status`.
    """

    recording_id: str
    camera_id: str | None
    channel: int | None
    start_original: datetime | None
    end_original: datetime | None
    duration_ms: int | None
    recording_type: str | None
    source_evidence_id: str | None
    source_region: str
    source_offset: int
    status: CPPlusParseStatus
    parser_version: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    raw_timestamp: int | None = None
    timestamp_source: str | None = None
    timestamp_interpretation: str | None = None
    timestamp_status: CPVTimestampStatus = CPVTimestampStatus.NOT_PRESENT
    analysis: CPVFileAnalysis | None = None


@dataclass(frozen=True)
class CPPlusEnumerationResult:
    """Result of enumerating recordings from a CP Plus evidence source.

    Phase 8 task scope, section 11 ("Partial Parsing"): `status` may be
    `SUPPORTED_PARTIAL` while `recordings` still holds every recording that
    *could* be validated — corrupted/unreadable portions are reported via
    `affected_regions`/`warnings`, never silently dropped.
    """

    status: CPPlusParseStatus
    recordings: list[CPPlusRecordingRecord]
    discovered_count: int
    affected_regions: list[str]
    warnings: list[str]
    parser_version: str
    reason: str


def to_recording_fields(record: CPPlusRecordingRecord) -> dict[str, object]:
    """Map one `CPPlusRecordingRecord` onto `app.models.recording.Recording`'s field names.

    Master Specification Section 9 ("Normalized Output"): CP Plus produces
    the same common evidence shape every later phase already consumes,
    rather than a CP Plus-only downstream model. Returns a plain dict of
    constructor kwargs (everything except `evidence_id`, which the caller
    assigns) so this module never needs to import SQLAlchemy.

    Fields this analysis could not validate (codec/width/height/fps — see
    CPV_ANALYSIS_REPORT.md section 15, item 1: the SPS was never actually
    bit-decoded) stay `None` here even though H.265 NAL presence is
    detected elsewhere on `record.analysis` — that richer, CP-Plus-specific
    diagnostic detail intentionally has no column on the common `Recording`
    model and is not persisted by this mapping (per this task's
    instruction not to add a CP-Plus-only database schema).

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
        "codec": None,
        "container": None,
        "width": None,
        "height": None,
        "fps": None,
        "source_location": f"{record.source_region}@offset={record.source_offset}",
        "recovery_status": None,
        "recovery_method": None,
        "confidence": record.confidence,
        "artifact_id": None,
    }
