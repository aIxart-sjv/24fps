"""
CP Plus HEVC (H.265) elementary-stream reconstruction (Phase 9).

Master Specification Section 16 ("FFmpeg must NOT be treated as the
proprietary filesystem parser") and Section 20 (Media Artifact Model):
this module's job stops at "produce a valid Annex-B HEVC elementary
stream from the CPV records this adapter already understands" — it never
decodes, re-encodes, or hands bytes to FFmpeg itself. Containerizing the
resulting stream into a playable file is `app.media.demux`'s job, layered
on top of this module's output, per Section 16's adapter/common-engine
split.

Byte-level basis for the record-family -> elementary-stream mapping below
(re-verified directly against the real evidence during Phase 9
implementation, not merely inherited from the Phase 8 analysis pass):

  - `KEYFRAME_MARKER` (type-tag low byte 0xFD) records: every occurrence
    sampled (not just the file-opening one) carries a complete
    VPS+SPS+PPS+IDR Annex-B NAL sequence in its body — consistent with an
    encoder that re-emits parameter sets at every GOP boundary for
    random-access playback. This is a broader finding than Phase 8's
    models.py docstring states (which — by its own admission — verified
    only the smallest, 2-second file); nothing here contradicts Phase 8's
    frozen structural parsing, this module simply reads whatever NAL
    units `container.find_annexb_nal_units` actually finds in each
    record's body, so it is correct under either characterization.
  - `VIDEO_FRAME` (0xFC) records: every occurrence sampled carries exactly
    one Annex-B NAL (`TRAIL_R`, an ordinary reference slice).
  - `VIDEO_FIXED_AUXILIARY` (0xF0) records: fixed 368-byte body, and in a
    ~4,600-record real sample, 1941/1956 (99.2%) contained zero `00 00
    01` byte sequences; the ~1% that did contain one decoded to
    HEVC NAL-type values (2, 7, 12, 13, 15, 27, 29, 51, 52, 62) that are
    not standard slice/parameter-set types for this stream — consistent
    with coincidental 3-byte pattern matches inside opaque fixed-format
    binary data, not real NAL units. This family's purpose remains
    "not established" (see `app.adapters.cp_plus.models`); it is
    deliberately excluded from the reconstructed elementary stream rather
    than guessed to be audio/video.
  - `TELEMETRY` (0xF1 family) records: JSON/binary side-channel data
    (Section 8 of CPV_ANALYSIS_REPORT.md), never video.

Reconstruction never assumes ordering beyond what the container itself
guarantees: records are walked in ascending file-offset order (the same
order `container.iter_cpv_records` yields them), which is the only
ordering this format provides — there is no per-frame presentation
timestamp in the container to independently confirm playback order
against (see `CPVTimestampStatus`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import IO

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.cp_plus.container import (
    find_annexb_nal_units,
    iter_cpv_records,
    read_record_body,
)
from app.adapters.cp_plus.models import CPVRecordFamily, CPVRecordValidity

#: Record families whose body is treated as (part of) the HEVC elementary
#: stream once an Annex-B start code is found in it.
_VIDEO_FAMILIES = frozenset({CPVRecordFamily.VIDEO_FRAME, CPVRecordFamily.KEYFRAME_MARKER})


@dataclass(frozen=True)
class CPVExtractionResult:
    """Outcome of reconstructing one CPV file's HEVC elementary stream.

    Every count here is a direct tally of what was actually walked and
    written — never estimated from file size or nominal frame rate
    (Master Specification Section 6).
    """

    segment_label: str
    frames_written: int
    keyframes_written: int
    bytes_written: int
    skipped_video_fixed_auxiliary: int
    skipped_telemetry: int
    skipped_unrecognized: int
    frames_missing_nal: int
    truncated: bool
    corrupted: bool
    warnings: list[str] = field(default_factory=list)


def extract_hevc_elementary_stream(
    reader: EvidenceStorageReader, output: IO[bytes], *, segment_label: str
) -> CPVExtractionResult:
    """Walk one CPV file's records and append its HEVC Annex-B bytes to `output`.

    Streams record-by-record through the same bounded-read
    `container.iter_cpv_records`/`read_record_body` primitives Phase 8
    uses for analysis — this never reads the whole file into memory, and
    `output` is written to incrementally so the caller can concatenate
    multiple segments into one continuous elementary stream file without
    holding any of them fully in memory either (Master Specification
    Section 60).

    Only the bytes from a video-bearing record's first found Annex-B
    start code onward are written — the leading vendor-private per-record
    fields (record-timestamp echo and other undecoded bytes documented in
    CPV_ANALYSIS_REPORT.md section 5) are stripped, since they are not
    part of the HEVC bitstream. The NAL bytes themselves are copied
    verbatim, byte-for-byte, never re-encoded or altered.

    Args:
        reader: An already-open evidence reader for one CPV file.
        output: A writable binary stream to append this segment's
            elementary-stream bytes to. Not closed by this function.
        segment_label: Caller-chosen identifier for this segment (e.g.
            its filename), used only in `warnings` text.

    Returns:
        A `CPVExtractionResult` describing what was written and skipped.
        Never raises for truncated/corrupted input — see `truncated`/
        `corrupted`/`warnings` instead, matching every other CP Plus
        parsing entry point's error-handling contract.
    """
    frames_written = 0
    keyframes_written = 0
    bytes_written = 0
    skipped_aux = 0
    skipped_telemetry = 0
    skipped_unrecognized = 0
    frames_missing_nal = 0
    truncated = False
    corrupted = False
    warnings: list[str] = []

    for record in iter_cpv_records(reader):
        if record.validity != CPVRecordValidity.VALID:
            warnings.extend(record.warnings)
            if record.validity in (
                CPVRecordValidity.TRUNCATED_HEADER,
                CPVRecordValidity.LENGTH_EXCEEDS_CONTAINER,
            ):
                truncated = True
            elif record.validity in (
                CPVRecordValidity.BAD_MAGIC,
                CPVRecordValidity.INVALID_LENGTH,
                CPVRecordValidity.FOOTER_MISMATCH,
            ):
                corrupted = True
            # CPVRecordValidity.TRAILING_PADDING: expected end of real
            # records, neither truncated nor corrupted.
            break

        if record.family in _VIDEO_FAMILIES:
            body = read_record_body(reader, record)
            nal_units = find_annexb_nal_units(body)
            if not nal_units:
                frames_missing_nal += 1
                warnings.append(
                    f"{segment_label}: no Annex-B NAL start code found in "
                    f"{record.family.value} record at offset {record.offset}; frame omitted "
                    "from the elementary stream, not fabricated"
                )
                continue
            chunk = body[nal_units[0].offset_in_body :]
            output.write(chunk)
            bytes_written += len(chunk)
            frames_written += 1
            if record.family == CPVRecordFamily.KEYFRAME_MARKER:
                keyframes_written += 1
        elif record.family == CPVRecordFamily.VIDEO_FIXED_AUXILIARY:
            skipped_aux += 1
        elif record.family == CPVRecordFamily.TELEMETRY:
            skipped_telemetry += 1
        else:
            # CPVRecordFamily.UNKNOWN with VALID framing does not occur in
            # the validated evidence (family is derived deterministically
            # from a type-tag low byte this format's four known families
            # already cover). If it ever does, it is a genuinely novel
            # finding — counted and warned about explicitly, never
            # silently dropped (Master Specification Section 11).
            skipped_unrecognized += 1
            warnings.append(
                f"{segment_label}: unrecognized record family for type_tag "
                f"0x{record.type_tag:x} at offset {record.offset}; not written to the "
                "elementary stream, not fabricated"
            )

    return CPVExtractionResult(
        segment_label=segment_label,
        frames_written=frames_written,
        keyframes_written=keyframes_written,
        bytes_written=bytes_written,
        skipped_video_fixed_auxiliary=skipped_aux,
        skipped_telemetry=skipped_telemetry,
        skipped_unrecognized=skipped_unrecognized,
        frames_missing_nal=frames_missing_nal,
        truncated=truncated,
        corrupted=corrupted,
        warnings=warnings,
    )
