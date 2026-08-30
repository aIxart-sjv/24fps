"""
CP Plus vendor-specific recovery (Phase 10, "Recovery Engine").

Implements the vendor-specific pieces of the layered recovery model
(Master Specification Section 21) for the validated "ADIT-v1" CPV
structure, reusing Phase 8/9 parsing exactly as it stands — nothing here
re-walks records or re-detects NAL units independently:

  - damaged-recording recovery reuses
    `app.adapters.cp_plus.extraction.extract_hevc_elementary_stream`
    directly (Phase 9) and additionally walks the same record sequence a
    second time — a cheap, header/footer-only pass, no payload bytes read
    — via `container.iter_cpv_records` purely to collect each valid
    record's `counter` for continuity scoring;
  - fragment reconstruction reuses
    `app.adapters.cp_plus.session.link_cpv_session` (Phase 8) directly;
  - carving hands each candidate offset found by
    `app.recovery.carving.carve_by_signature` to the *existing*
    `container.iter_cpv_records(reader, start_offset=candidate)` to
    validate it — carving never reimplements record-framing logic.

CONTROLLED-EVIDENCE STATUS: the real 13-file evidence package contains no
deleted recordings and no raw/unallocated disk image. `find_deleted_recordings`
below is therefore a **RECOVERY FRAMEWORK / UNVALIDATED PATH** — it is
real, tested code that reports an honest, evidence-based `UNSUPPORTED`
outcome (Phase 8's analysis found no index/seek-table in this container
format at all), never a fabricated deleted-recording recovery. By
contrast, damaged-recording recovery below is **REAL VALIDATED RECOVERY**:
demonstrated against the real evidence package's own genuinely truncated
trailing record (see `tests/test_cp_plus_recovery_real_evidence_integration.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import IO

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.cp_plus.container import iter_cpv_records
from app.adapters.cp_plus.extraction import extract_hevc_elementary_stream
from app.adapters.cp_plus.models import (
    RECORD_MAGIC,
    CPVRecordFamily,
    CPVRecordValidity,
    CPVSegmentDescriptor,
    CPVSessionLinkResult,
)
from app.adapters.cp_plus.session import link_cpv_session
from app.recovery import RecoveryStatus
from app.recovery.carving import carve_by_signature
from app.recovery.confidence import ConfidenceFactor, compute_confidence
from app.recovery.continuity import measure_counter_continuity

#: The exact, literal statement the Phase 10 task requires when deleted-
#: recording recovery has not been validated against real deleted CP Plus
#: evidence (task section 15).
DELETED_RECOVERY_NOT_VALIDATED_STATEMENT = (
    "Deleted-record recovery not validated against real deleted CP Plus evidence."
)

#: Record families whose `counter` field forms one shared, per-frame
#: incrementing sequence — confirmed by direct byte inspection of the real
#: evidence: `VIDEO_FRAME`/`KEYFRAME_MARKER` counters increment by exactly
#: 1 per record, while `VIDEO_FIXED_AUXILIARY` (`0xF0`) counters run in a
#: *separate*, differently-based incrementing sequence of their own.
#: Continuity must only ever be measured within one such family, never
#: across mixed families (mixing them makes every "step" a large,
#: meaningless jump).
_VIDEO_FAMILIES = frozenset({CPVRecordFamily.VIDEO_FRAME, CPVRecordFamily.KEYFRAME_MARKER})

#: Evidence basis: CPV_ANALYSIS_REPORT.md section 13 ("No footer/index/
#: seek-table was found at the tail of the sampled files") — the ADIT-v1
#: container carries no discoverable index/deletion-marker structure this
#: adapter could search, for any of the 13 real evidence files analyzed.
_NO_INDEX_REASON = (
    "no deletion-marker or index/seek-table structure has been evidence-validated for the "
    "ADIT-v1 container (CPV_ANALYSIS_REPORT.md section 13); this is a RECOVERY FRAMEWORK / "
    "UNVALIDATED PATH, not a validated deleted-recording recovery capability. "
    f"{DELETED_RECOVERY_NOT_VALIDATED_STATEMENT}"
)


@dataclass(frozen=True)
class CPVDeletedRecordingSearchResult:
    """Outcome of searching for deleted-but-referenced CPV recordings."""

    status: RecoveryStatus
    reason: str


def find_deleted_cpv_recordings() -> CPVDeletedRecordingSearchResult:
    """Search for deleted-but-still-referenced recordings in the ADIT-v1 container.

    Always reports `UNSUPPORTED`: Phase 8's byte-level analysis (see
    module docstring) found no index/seek-table structure of any kind in
    this container format, on any of the 13 real evidence files analyzed
    — there is nothing evidence-validated to search. This is deterministic
    and does not depend on the bound evidence's contents.

    Returns:
        A `CPVDeletedRecordingSearchResult` with `status=UNSUPPORTED`.
    """
    return CPVDeletedRecordingSearchResult(
        status=RecoveryStatus.UNSUPPORTED, reason=_NO_INDEX_REASON
    )


@dataclass(frozen=True)
class CPVRecoveryResult:
    """Outcome of attempting to recover one (possibly damaged) CPV segment."""

    segment_label: str
    status: RecoveryStatus
    bytes_recovered: int
    frames_recovered: int
    frame_continuity: float | None
    confidence: float | None
    confidence_basis: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def recover_damaged_cpv_segment(
    reader: EvidenceStorageReader, output: IO[bytes], *, segment_label: str
) -> CPVRecoveryResult:
    """Recover the valid portion of a (possibly damaged) CPV segment's video.

    Reuses `extract_hevc_elementary_stream` (Phase 9) for the actual byte
    reconstruction — this function adds nothing to *what* is written, only
    to *how the outcome is classified and scored* for recovery purposes.

    Args:
        reader: An already-open evidence reader for one CPV file.
        output: A writable binary stream to receive the recovered
            elementary-stream bytes. Not closed by this function.
        segment_label: Caller-chosen identifier for this segment.

    Returns:
        A `CPVRecoveryResult`. `status` is `RECOVERED` only when the
        record walk reached the end of file (or a benign, expected
        trailing-padding stop — see `CPVRecordValidity.TRAILING_PADDING`)
        with no truncation/corruption anywhere and at least one frame
        written; `PARTIAL` when some real, valid frames were written but
        the walk stopped early at a genuinely truncated/corrupted record;
        `NO_RECOVERY_FOUND` when zero video bytes could be recovered at
        all. Never raises.
    """
    extraction_result = extract_hevc_elementary_stream(reader, output, segment_label=segment_label)

    counters: list[int] = []
    for record in iter_cpv_records(reader):
        if record.validity != CPVRecordValidity.VALID:
            break
        if record.family in _VIDEO_FAMILIES and record.counter is not None:
            counters.append(record.counter)
    continuity = measure_counter_continuity(counters)

    if extraction_result.bytes_written == 0:
        status = RecoveryStatus.NO_RECOVERY_FOUND
    elif extraction_result.truncated or extraction_result.corrupted:
        status = RecoveryStatus.PARTIAL
    else:
        status = RecoveryStatus.RECOVERED

    total_video_records = extraction_result.frames_written + extraction_result.frames_missing_nal
    factors = [
        ConfidenceFactor(
            name="valid_headers",
            weight=2.0,
            value=(
                1.0
                if extraction_result.keyframes_written > 0
                else (0.0 if extraction_result.frames_written > 0 else None)
            ),
            basis=(
                f"{extraction_result.keyframes_written} keyframe-marker record(s) with "
                "VPS/SPS/PPS/IDR NAL units found"
            ),
        ),
        ConfidenceFactor(
            name="frame_continuity",
            weight=1.0,
            value=continuity.continuity_fraction,
            basis=(
                f"{continuity.continuous_steps}/{continuity.total_steps} adjacent record "
                "counters advance by exactly 1"
                if continuity.total_steps
                else "fewer than 2 valid records; continuity not measurable"
            ),
        ),
        ConfidenceFactor(
            name="nal_presence",
            weight=1.0,
            value=(
                (1.0 - (extraction_result.frames_missing_nal / total_video_records))
                if total_video_records
                else None
            ),
            basis=(
                f"{extraction_result.frames_missing_nal}/{total_video_records} video-bearing "
                "record(s) had no recoverable NAL data"
            ),
        ),
    ]
    confidence_result = compute_confidence(factors)

    return CPVRecoveryResult(
        segment_label=segment_label,
        status=status,
        bytes_recovered=extraction_result.bytes_written,
        frames_recovered=extraction_result.frames_written,
        frame_continuity=continuity.continuity_fraction,
        confidence=confidence_result.confidence,
        confidence_basis=confidence_result.basis,
        warnings=list(extraction_result.warnings),
    )


def reconstruct_cpv_fragments(descriptors: list[CPVSegmentDescriptor]) -> CPVSessionLinkResult:
    """Reconstruct the correct order/relationship of a set of CPV segments.

    A thin, evidence-preserving wrapper: sorts `descriptors` by their
    outer-header start counter (the *actual* reordering step — the
    caller's original ordering, e.g. filename order, is not trusted) and
    hands the sorted sequence to Phase 8's own
    `app.adapters.cp_plus.session.link_cpv_session`, unmodified, to
    determine gaps/overlaps/duplicates.

    Args:
        descriptors: Segment descriptors for a set of CPV files believed
            to belong to one session, in any order.

    Returns:
        The `CPVSessionLinkResult` for the counter-sorted sequence.
        Descriptors with `readable=False` (no usable counters) sort last
        and are still included — `link_cpv_session` reports them as
        `UNKNOWN` links, never silently dropped.
    """
    ordered = sorted(
        descriptors,
        key=lambda d: (not d.readable, d.start_counter if d.start_counter is not None else 0),
    )
    return link_cpv_session(ordered)


@dataclass(frozen=True)
class CPVCarvedRecord:
    """One record boundary found by signature scanning, independent of the
    normal sequential record walk."""

    offset: int
    valid: bool
    family: str | None
    also_found_by_sequential_walk: bool


@dataclass(frozen=True)
class CPVCarvingResult:
    """Outcome of scanning a CPV container for `CPAV` record magics."""

    candidates_found: int
    candidates_valid: int
    records: list[CPVCarvedRecord] = field(default_factory=list)


def carve_cpv_records(
    reader: EvidenceStorageReader, *, known_valid_offsets: frozenset[int] = frozenset()
) -> CPVCarvingResult:
    """Scan a CPV container for `CPAV` record magics via bounded signature scanning.

    Every candidate offset found is validated by handing it to the
    *existing* `container.iter_cpv_records(reader, start_offset=candidate)`
    (taking only the first record it yields) — carving never re-derives
    record-framing rules itself, only locates candidate start points a
    sequential walk (which requires an unbroken chain of length fields)
    might not reach, e.g. past a corrupted record earlier in the file.

    Args:
        reader: An already-open evidence reader.
        known_valid_offsets: Offsets already confirmed valid by a normal
            sequential walk (e.g. `container.analyze_cpv_file`), purely so
            the result can report which carved candidates are genuinely
            *new* finds versus ones sequential walking already covers.

    Returns:
        A `CPVCarvingResult` listing every candidate found and whether it
        validated as a real record.
    """
    records: list[CPVCarvedRecord] = []
    valid_count = 0
    for offset in carve_by_signature(reader, RECORD_MAGIC):
        record = next(iter_cpv_records(reader, start_offset=offset), None)
        is_valid = record is not None and record.validity == CPVRecordValidity.VALID
        if is_valid:
            valid_count += 1
        records.append(
            CPVCarvedRecord(
                offset=offset,
                valid=is_valid,
                family=(record.family.value if record is not None else None),
                also_found_by_sequential_walk=offset in known_valid_offsets,
            )
        )
    return CPVCarvingResult(
        candidates_found=len(records), candidates_valid=valid_count, records=records
    )
