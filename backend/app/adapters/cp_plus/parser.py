"""
CP Plus parser (Phase 8 / Fourth Backend Milestone).
Phase 8 task scope, section 3 ("Parser Contract"):

    "At minimum, it should be capable of: validating the input structure;
    identifying the relevant storage regions; enumerating recordings where
    supported; extracting recording metadata where available; returning
    structured unsupported/corrupt results."

VALIDATION STATUS: this parser implements the "ADIT-v1" container format
established by read-only, byte-level analysis of a real, hash-verified CP
Plus evidence package (see `app.adapters.cp_plus.models`'s module
docstring for exactly which NVR/firmware/camera it was validated against).
`enumerate_recordings` produces one real `CPPlusRecordingRecord` per
matched file — built entirely from what `app.adapters.cp_plus.container`
actually found in that file's bytes, never fabricated. Evidence that does
not match the validated "ADIT-v1" signature still honestly reports
UNSUPPORTED/UNKNOWN, exactly as before.

Every read goes through `EvidenceStorageReader.read(offset, length)` with
validated, bounded offsets/lengths (Phase 8 task scope, sections 6-7) —
never a whole-container read — so this stays safe against multi-terabyte
evidence and never crashes on a malformed/truncated structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.cp_plus.container import analyze_cpv_file, parse_cp_plus_export_filename
from app.adapters.cp_plus.detector import detect_cp_plus_structure
from app.adapters.cp_plus.extraction import CPVExtractionResult, extract_hevc_elementary_stream
from app.adapters.cp_plus.models import (
    OUTER_HEADER_SIZE,
    CPPlusDetectionResult,
    CPPlusEnumerationResult,
    CPPlusParseStatus,
    CPPlusRecordingRecord,
    CPVFileAnalysis,
    CPVFilenameInfo,
    CPVTimestampStatus,
)

# Version of this parser implementation (Master Specification Section 59,
# "store parser version"). No longer carries an "-unvalidated" suffix: this
# parser has parsed a real, controlled CP Plus fixture successfully (see
# module docstring) — but it is validated against exactly one
# NVR/firmware/camera combination, never treated as universal CP Plus
# support (Master Specification Section 17).
PARSER_VERSION = "0.2.0"

# No single bounded read this parser issues may exceed this size. Chosen
# generously above any plausible CP Plus header/index structure while
# staying far below "load the whole image" territory (Master Specification
# Section 60: "Do not load a multi-terabyte image entirely into RAM").
MAX_SINGLE_READ = 16 * 1024 * 1024

_UNSUPPORTED_STATUSES = frozenset({CPPlusParseStatus.UNKNOWN, CPPlusParseStatus.UNSUPPORTED})

_TIMESTAMP_INTERPRETATION = (
    "raw little-endian 32-bit counter read from the outer header (offset 8 = segment start, "
    "offset 12 = segment end); confirmed to chain exactly across adjacent real segments "
    "(one file's end counter equals the next file's start counter), but its absolute value "
    "decodes as a Unix timestamp to a date that does NOT match this evidence's known "
    "real-world recording date — it is NOT a validated real-world timestamp and must not be "
    "treated as one. See CPV_ANALYSIS_REPORT.md section 6."
)


def bounded_read(reader: EvidenceStorageReader, offset: int, length: int) -> bytes:
    """Validate and perform one bounded read against `reader`.

    Args:
        reader: The evidence reader to read from.
        offset: Zero-based byte offset. Must be non-negative and not
            beyond the container's size.
        length: Number of bytes requested. Must be non-negative and not
            exceed `MAX_SINGLE_READ`.

    Returns:
        The bytes read (possibly shorter than `length` at end-of-container
        — see `EvidenceStorageReader.read`).

    Raises:
        ValueError: If `offset`/`length` is negative, `length` exceeds
            `MAX_SINGLE_READ`, or `offset` is beyond the container size.
    """
    if offset < 0:
        raise ValueError(f"offset must be non-negative, got {offset}")
    if length < 0:
        raise ValueError(f"length must be non-negative, got {length}")
    if length > MAX_SINGLE_READ:
        raise ValueError(
            f"requested read length {length} exceeds this parser's bounded-read limit of "
            f"{MAX_SINGLE_READ} bytes; the CP Plus parser never issues unbounded reads"
        )
    size = reader.size()
    if offset > size:
        raise ValueError(f"offset {offset} is beyond the evidence container size ({size} bytes)")
    return reader.read(offset, length)


def _filename_info(reader: EvidenceStorageReader) -> CPVFilenameInfo | None:
    """Best-effort filename-derived info, from whatever `reader.metadata()` exposes.

    Returns `None` whenever the reader carries no `source_path` metadata,
    or that path's filename does not match the expected export naming
    convention — never a guessed value.
    """
    source_path = reader.metadata().get("source_path")
    if not isinstance(source_path, str) or not source_path:
        return None
    return parse_cp_plus_export_filename(Path(source_path).name)


def _recording_id(
    reader: EvidenceStorageReader,
    filename_info: CPVFilenameInfo | None,
    source_evidence_id: str | None,
) -> str:
    source_path = reader.metadata().get("source_path")
    if filename_info is not None and isinstance(source_path, str) and source_path:
        return Path(source_path).stem
    return f"CPPLUS-ADIT-V1-{source_evidence_id or 'UNKNOWN'}"


def _status_from_analysis(analysis: CPVFileAnalysis) -> CPPlusParseStatus:
    if analysis.record_count == 0:
        return (
            CPPlusParseStatus.SUPPORTED_CORRUPTED
            if analysis.corrupted
            else CPPlusParseStatus.SUPPORTED_PARTIAL
        )
    if analysis.corrupted or analysis.truncated:
        return CPPlusParseStatus.SUPPORTED_PARTIAL
    return CPPlusParseStatus.SUPPORTED_VALID


def _confidence_from_status(status: CPPlusParseStatus, analysis: CPVFileAnalysis) -> float:
    """A conservative, evidence-based confidence value — never a fabricated number.

    Master Specification Section 22: confidence must be based on actual
    evidence. Here that evidence is simply "how much of the record
    sequence parsed cleanly": 1.0 only for a fully clean walk with at
    least one record and no warnings; scaled down for any partial/
    corrupted outcome; 0.0 when nothing could be parsed at all.
    """
    if status == CPPlusParseStatus.SUPPORTED_VALID and analysis.record_count > 0:
        return 1.0 if not analysis.warnings else 0.9
    if status == CPPlusParseStatus.SUPPORTED_PARTIAL and analysis.record_count > 0:
        return 0.5
    return 0.0


def _build_recording_record(
    reader: EvidenceStorageReader,
    detection: CPPlusDetectionResult,
    source_evidence_id: str | None,
) -> CPPlusRecordingRecord:
    analysis = analyze_cpv_file(reader)
    status = _status_from_analysis(analysis)
    filename_info = _filename_info(reader)
    outer_header = analysis.outer_header

    warnings: list[str] = list(analysis.warnings)
    channel: int | None = None
    start_original = None
    end_original = None
    duration_ms = None
    if filename_info is not None:
        channel = filename_info.channel
        start_original = filename_info.start_original
        end_original = filename_info.end_original
        if start_original is not None and end_original is not None:
            duration_ms = int((end_original - start_original).total_seconds() * 1000)
        warnings.append(
            "channel/start_original/end_original are derived from the export filename, not "
            "from the CPV binary structure — no channel/camera-ID field has been located in "
            "the container bytes (see CPV_ANALYSIS_REPORT.md section 7)"
        )
    else:
        warnings.append(
            "no export filename was available or it did not match the expected naming "
            "convention; channel/start_original/end_original are Not Determined"
        )

    raw_timestamp = outer_header.start_counter if outer_header is not None else None
    timestamp_status = (
        CPVTimestampStatus.RAW_COUNTER_UNVALIDATED
        if raw_timestamp is not None
        else CPVTimestampStatus.NOT_PRESENT
    )

    if not analysis.nal_units:
        warnings.append(
            "no HEVC/H.265 NAL start code was found in the body of the first keyframe-marker "
            "record scanned; H.265 presence could not be confirmed for this file"
        )
    if analysis.family_histogram:
        warnings.append(f"record family histogram: {analysis.family_histogram}")

    return CPPlusRecordingRecord(
        recording_id=_recording_id(reader, filename_info, source_evidence_id),
        camera_id=None,
        channel=channel,
        start_original=start_original,
        end_original=end_original,
        duration_ms=duration_ms,
        recording_type=None,
        source_evidence_id=source_evidence_id,
        source_region="cpv_container",
        source_offset=0,
        status=status,
        parser_version=PARSER_VERSION,
        confidence=_confidence_from_status(status, analysis),
        warnings=warnings,
        raw_timestamp=raw_timestamp,
        timestamp_source="cpv_outer_header_offset_8" if raw_timestamp is not None else None,
        timestamp_interpretation=_TIMESTAMP_INTERPRETATION if raw_timestamp is not None else None,
        timestamp_status=timestamp_status,
        analysis=analysis,
    )


class CPPlusParser:
    """Parses CP Plus evidence through the common `EvidenceStorageReader` abstraction.

    VALIDATED SCOPE: the "ADIT-v1" container format (see module docstring).
    `validate_structure` and `enumerate_recordings` perform real,
    bounded/streaming parsing against evidence matching that signature;
    anything else still honestly reports UNSUPPORTED/UNKNOWN.
    """

    def __init__(
        self, reader: EvidenceStorageReader, *, source_evidence_id: str | None = None
    ) -> None:
        """
        Args:
            reader: An already-open `EvidenceStorageReader` for the evidence
                to parse. Not closed by this class — the caller owns its
                lifecycle.
            source_evidence_id: The evidence item's ID, attached to any
                recording records produced (Master Specification Section 6:
                every `Recording` traces back to its source evidence).
        """
        self._reader = reader
        self._source_evidence_id = source_evidence_id

    def validate_structure(self) -> CPPlusDetectionResult:
        """Answer "does this evidence match a validated CP Plus structure?"."""
        return detect_cp_plus_structure(self._reader)

    def identify_storage_regions(self) -> list[str]:
        """Return the vendor-specific storage regions this parser can identify.

        Empty unless `validate_structure()` confirms the "ADIT-v1"
        signature — an unidentified region is never reported as a guessed
        one.
        """
        detection = self.validate_structure()
        if detection.status in _UNSUPPORTED_STATUSES:
            return []
        size = self._reader.size()
        return [
            f"outer_header@0-{min(OUTER_HEADER_SIZE, size)}",
            f"records@{OUTER_HEADER_SIZE}-{size}",
        ]

    def analyze_container(self) -> CPVFileAnalysis:
        """Run the full bounded/streaming record-structure analysis directly.

        Unlike `enumerate_recordings`, this does not gate on
        `validate_structure()` first — the underlying walk
        (`app.adapters.cp_plus.container.analyze_cpv_file`) is safe against
        any input regardless of whether the outer magic matched, which is
        useful for tests and diagnostics that want the raw structural
        result without the adapter-level UNSUPPORTED short-circuit.

        Returns:
            A `CPVFileAnalysis`.
        """
        return analyze_cpv_file(self._reader)

    def enumerate_recordings(self) -> CPPlusEnumerationResult:
        """Enumerate recordings discoverable from this CPV file.

        Returns:
            A `CPPlusEnumerationResult`. When `validate_structure()` does
            not confirm the "ADIT-v1" structure, this returns an empty
            recording list carrying that same status/reason forward.
            Otherwise it returns exactly one `CPPlusRecordingRecord` for
            this file (a CPV file is one session segment, not a
            multi-recording container — see
            `app.adapters.cp_plus.session` for the separate multi-file
            session-linking step), built entirely from what
            `app.adapters.cp_plus.container.analyze_cpv_file` actually
            found; nothing is fabricated when a field could not be
            determined (Master Specification Section 6).
        """
        detection = self.validate_structure()
        if detection.status in _UNSUPPORTED_STATUSES:
            return CPPlusEnumerationResult(
                status=detection.status,
                recordings=[],
                discovered_count=0,
                affected_regions=[],
                warnings=list(detection.warnings),
                parser_version=PARSER_VERSION,
                reason=detection.reason,
            )

        recording = _build_recording_record(self._reader, detection, self._source_evidence_id)
        analysis = recording.analysis
        affected_regions: list[str] = []
        if analysis is not None and (analysis.truncated or analysis.corrupted):
            affected_regions.append(f"records after offset {analysis.last_valid_record_end}")

        if recording.status == CPPlusParseStatus.SUPPORTED_VALID:
            reason = (
                f"parsed {analysis.record_count if analysis else 0} valid record(s) from a "
                f"{analysis.container_size if analysis else 0}-byte ADIT-v1 container"
            )
        elif recording.status == CPPlusParseStatus.SUPPORTED_PARTIAL:
            reason = (
                f"parsed {analysis.record_count if analysis else 0} valid record(s) before "
                "encountering truncated/corrupted data; partial result reported rather than "
                "silently dropped"
            )
        else:
            reason = "ADIT-v1 outer header matched, but no valid record could be parsed"

        return CPPlusEnumerationResult(
            status=recording.status,
            recordings=[recording],
            discovered_count=1,
            affected_regions=affected_regions,
            warnings=list(recording.warnings),
            parser_version=PARSER_VERSION,
            reason=reason,
        )

    def extract_elementary_stream(
        self, output: IO[bytes], *, segment_label: str | None = None
    ) -> CPVExtractionResult:
        """Reconstruct this CPV file's HEVC Annex-B elementary stream into `output`.

        Phase 9 ("Recording extraction + FFmpeg"): consumes exactly the
        NAL-unit/record structures Phase 8 already validates — see
        `app.adapters.cp_plus.extraction` for the record-family mapping
        and its evidence basis. Gated on `validate_structure()` first, the
        same way `enumerate_recordings` is, so an evidence source that
        never matched "ADIT-v1" is never walked as if it had.

        Args:
            output: A writable binary stream to append this file's
                elementary-stream bytes to. Not closed by this method —
                callers building a multi-segment session stream keep it
                open across several `extract_elementary_stream` calls.
            segment_label: Caller-chosen identifier for this segment, used
                only in warning text. Defaults to this parser's
                `source_evidence_id`, or `"unknown"` if neither is set.

        Returns:
            A `CPVExtractionResult`. If `validate_structure()` does not
            confirm the "ADIT-v1" structure, this returns an all-zero
            result carrying a single explanatory warning rather than
            walking unrecognized bytes.
        """
        label = segment_label or self._source_evidence_id or "unknown"
        detection = self.validate_structure()
        if detection.status in _UNSUPPORTED_STATUSES:
            return CPVExtractionResult(
                segment_label=label,
                frames_written=0,
                keyframes_written=0,
                bytes_written=0,
                skipped_video_fixed_auxiliary=0,
                skipped_telemetry=0,
                skipped_unrecognized=0,
                frames_missing_nal=0,
                truncated=False,
                corrupted=False,
                warnings=[
                    f"{label}: not extracted — {detection.reason}",
                ],
            )
        return extract_hevc_elementary_stream(self._reader, output, segment_label=label)
