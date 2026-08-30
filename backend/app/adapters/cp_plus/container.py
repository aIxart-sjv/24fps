"""
CP Plus CPV container/record parsing (Phase 8 implementation).

Implements exactly the structure established by read-only, byte-level
analysis of the real evidence package at
`~/Documents/24fps-evidence/cp-plus-2026-08-28/` (see
`analysis/CPV_ANALYSIS_REPORT.md` there, and `app.adapters.cp_plus.models`'
module docstring for the validated device identity this is scoped to).

Container shape:

    offset 0                 offset 1024              EOF
    +------------------------+------------------------------+
    | outer "ADIT" header    | sequence of CPAV records      |
    | (1024 bytes, fixed)    | (length-prefixed and -suffixed)|
    +------------------------+------------------------------+

Each record is exactly `record.length` bytes, laid out as:

    [4]  b"CPAV"                     magic
    [4]  type_tag        (LE u32)
    [4]  counter          (LE u32)
    [4]  length            (LE u32)  -- TOTAL record size, header..footer inclusive
    [.. length-24 bytes ..]           body (first 4 bytes: record_timestamp)
    [4]  b"cpav"                     footer magic
    [4]  length (repeated) (LE u32)  footer length-echo

This was verified with a full length-jump walk across all 13 real evidence
files (tens of thousands of records) with **zero** footer mismatches. The
formula (record size == the record's own `length` field) lets a parser
jump directly from one record to the next in O(1), which is what
`iter_cpv_records` below does — it never scans for the next magic byte by
brute force.

All reads go through `EvidenceStorageReader.read(offset, length)` with
sizes bounded well below `MAX_RECORD_BODY_READ`; nothing in this module
ever reads a whole file into memory.
"""

from __future__ import annotations

import json
import re
import struct
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.cp_plus.models import (
    ADIT_MAGIC,
    MIN_RECORD_SIZE,
    OUTER_HEADER_SIZE,
    RECORD_FOOTER_MAGIC,
    RECORD_FOOTER_SIZE,
    RECORD_HEADER_SIZE,
    RECORD_MAGIC,
    CPVFileAnalysis,
    CPVFilenameInfo,
    CPVNalUnitInfo,
    CPVOuterHeader,
    CPVRecord,
    CPVRecordFamily,
    CPVRecordValidity,
    CPVTelemetryPayload,
    classify_record_family,
    hevc_nal_unit_name,
)

#: Never body-read more than this many bytes for a single record, matching
#: `app.adapters.cp_plus.parser.MAX_SINGLE_READ`'s bounded-read discipline.
MAX_RECORD_BODY_READ = 16 * 1024 * 1024

#: How many TELEMETRY-family records to fully decode per file. Bounded so a
#: file analysis pass stays cheap and fast regardless of how many telemetry
#: records the file actually contains (thousands, for the longest segment).
TELEMETRY_SAMPLE_LIMIT = 20

_ANNEX_B_START_CODE = b"\x00\x00\x01"
_ALL_FF = b"\xff\xff\xff\xff"

_EXPORT_FILENAME_RE = re.compile(
    r"^(?P<prefix>[A-Za-z0-9]+)_ch(?P<channel>\d+)_(?P<stream>[A-Za-z0-9]+)_"
    r"(?P<start>\d{14})_(?P<end>\d{14})\.cpv$",
    re.IGNORECASE,
)


def parse_outer_header(reader: EvidenceStorageReader) -> CPVOuterHeader:
    """Parse the 1024-byte outer "ADIT" header at offset 0.

    Args:
        reader: An already-open evidence reader.

    Returns:
        A `CPVOuterHeader`. Never raises for a short/malformed container —
        fields that could not be read stay `None`.
    """
    size = reader.size()
    header = reader.read(0, min(OUTER_HEADER_SIZE, size))
    if len(header) < 16:
        return CPVOuterHeader(
            magic_valid=False,
            version_field=b"",
            start_counter=None,
            end_counter=None,
            reserved_all_zero=None,
            bytes_read=len(header),
        )

    magic_valid = header[0:8] == ADIT_MAGIC
    version_field = bytes(header[4:8])
    start_counter, end_counter = struct.unpack_from("<II", header, 8)

    reserved_all_zero: bool | None = None
    if len(header) >= OUTER_HEADER_SIZE:
        reserved_all_zero = header[16:OUTER_HEADER_SIZE] == b"\x00" * (OUTER_HEADER_SIZE - 16)

    return CPVOuterHeader(
        magic_valid=magic_valid,
        version_field=version_field,
        start_counter=start_counter,
        end_counter=end_counter,
        reserved_all_zero=reserved_all_zero,
        bytes_read=len(header),
    )


def iter_cpv_records(
    reader: EvidenceStorageReader, *, start_offset: int = OUTER_HEADER_SIZE
) -> Iterator[CPVRecord]:
    """Walk a CPV file's records, one at a time, using the length-jump formula.

    Every record's fixed-size header (16 bytes) and footer (8 bytes) are
    read; body bytes are NOT read here (see `read_record_body` for that,
    invoked selectively by callers). This keeps the walk cheap even across
    a file with tens of thousands of records.

    The walk stops (does not raise) at the first record that is not fully
    well-formed — a truncated header, bad magic, an invalid/oversized
    length, or a footer mismatch — after yielding that record so the
    caller can see exactly where and why. There is no resynchronization
    scan: once framing is uncertain, guessing where the next record might
    start would not be evidence-driven.

    Args:
        reader: An already-open evidence reader.
        start_offset: Byte offset of the first record (defaults to right
            after the outer header).

    Yields:
        One `CPVRecord` per record found, in file order.
    """
    size = reader.size()
    offset = start_offset

    while offset < size:
        remaining = size - offset
        if remaining < RECORD_HEADER_SIZE:
            yield CPVRecord(
                offset=offset,
                type_tag=0,
                family=CPVRecordFamily.UNKNOWN,
                counter=None,
                length=None,
                record_timestamp=None,
                validity=CPVRecordValidity.TRUNCATED_HEADER,
                footer_valid=None,
                payload_offset=offset,
                payload_length=0,
                warnings=(
                    (
                        f"only {remaining} byte(s) remain at offset {offset}, fewer than the "
                        f"{RECORD_HEADER_SIZE}-byte record header"
                    ),
                ),
            )
            return

        header = reader.read(offset, RECORD_HEADER_SIZE)
        magic = header[0:4]

        if magic != RECORD_MAGIC:
            if magic == _ALL_FF:
                yield CPVRecord(
                    offset=offset,
                    type_tag=0,
                    family=CPVRecordFamily.UNKNOWN,
                    counter=None,
                    length=None,
                    record_timestamp=None,
                    validity=CPVRecordValidity.TRAILING_PADDING,
                    footer_valid=None,
                    payload_offset=offset,
                    payload_length=0,
                    warnings=(
                        (
                            f"0xFF fixed-block padding found at offset {offset} instead of a "
                            "record magic — treated as end-of-real-records, not corruption"
                        ),
                    ),
                )
            else:
                yield CPVRecord(
                    offset=offset,
                    type_tag=0,
                    family=CPVRecordFamily.UNKNOWN,
                    counter=None,
                    length=None,
                    record_timestamp=None,
                    validity=CPVRecordValidity.BAD_MAGIC,
                    footer_valid=None,
                    payload_offset=offset,
                    payload_length=0,
                    warnings=(
                        f"expected {RECORD_MAGIC!r} at offset {offset}, found {bytes(magic)!r}",
                    ),
                )
            return

        type_tag, counter, length = struct.unpack_from("<III", header, 4)
        family = classify_record_family(type_tag)

        if length < MIN_RECORD_SIZE:
            yield CPVRecord(
                offset=offset,
                type_tag=type_tag,
                family=family,
                counter=counter,
                length=length,
                record_timestamp=None,
                validity=CPVRecordValidity.INVALID_LENGTH,
                footer_valid=None,
                payload_offset=offset + RECORD_HEADER_SIZE,
                payload_length=0,
                warnings=(
                    (
                        f"declared length {length} at offset {offset} is smaller than the minimum "
                        f"possible record size ({MIN_RECORD_SIZE})"
                    ),
                ),
            )
            return

        if offset + length > size:
            overrun = offset + length - size
            yield CPVRecord(
                offset=offset,
                type_tag=type_tag,
                family=family,
                counter=counter,
                length=length,
                record_timestamp=None,
                validity=CPVRecordValidity.LENGTH_EXCEEDS_CONTAINER,
                footer_valid=None,
                payload_offset=offset + RECORD_HEADER_SIZE,
                payload_length=max(0, size - offset - RECORD_HEADER_SIZE),
                warnings=(
                    (
                        f"declared length {length} at offset {offset} extends {overrun} byte(s) "
                        f"past the container's end (size={size}); record is truncated"
                    ),
                ),
            )
            return

        footer_offset = offset + length - RECORD_FOOTER_SIZE
        footer = reader.read(footer_offset, RECORD_FOOTER_SIZE)
        expected_footer = RECORD_FOOTER_MAGIC + struct.pack("<I", length)
        footer_valid = footer == expected_footer

        payload_offset = offset + RECORD_HEADER_SIZE
        payload_length = length - RECORD_HEADER_SIZE - RECORD_FOOTER_SIZE

        record_timestamp: int | None = None
        if payload_length >= 4:
            ts_bytes = reader.read(payload_offset, 4)
            if len(ts_bytes) == 4:
                record_timestamp = struct.unpack("<I", ts_bytes)[0]

        warnings: tuple[str, ...] = ()
        if not footer_valid:
            warnings = (
                (
                    f"footer at offset {footer_offset} did not match expected "
                    f"{expected_footer!r} (got {bytes(footer)!r})"
                ),
            )

        record = CPVRecord(
            offset=offset,
            type_tag=type_tag,
            family=family,
            counter=counter,
            length=length,
            record_timestamp=record_timestamp,
            validity=CPVRecordValidity.VALID if footer_valid else CPVRecordValidity.FOOTER_MISMATCH,
            footer_valid=footer_valid,
            payload_offset=payload_offset,
            payload_length=payload_length,
            warnings=warnings,
        )
        yield record

        if not footer_valid:
            return
        offset += length


def read_record_body(
    reader: EvidenceStorageReader, record: CPVRecord, *, max_bytes: int = MAX_RECORD_BODY_READ
) -> bytes:
    """Read a validated record's body bytes, bounded to `max_bytes`.

    Args:
        reader: An already-open evidence reader.
        record: A `CPVRecord` yielded by `iter_cpv_records`.
        max_bytes: Hard cap on how much of the body to read.

    Returns:
        Up to `min(record.payload_length, max_bytes)` bytes starting at
        `record.payload_offset`. Empty if the record has no payload.
    """
    length = min(record.payload_length, max_bytes)
    if length <= 0:
        return b""
    return reader.read(record.payload_offset, length)


def find_annexb_nal_units(body: bytes) -> list[CPVNalUnitInfo]:
    """Find HEVC (H.265) Annex-B NAL units in `body` by their start codes.

    Only reports a NAL unit where a `00 00 01` start code was actually
    found, immediately followed by at least one byte to decode a NAL
    header from — never inferred from context.

    Args:
        body: Already bounded-read record body bytes.

    Returns:
        One `CPVNalUnitInfo` per start code found, in order.
    """
    units: list[CPVNalUnitInfo] = []
    for match in re.finditer(re.escape(_ANNEX_B_START_CODE), body):
        nal_header_offset = match.end()
        if nal_header_offset >= len(body):
            continue
        first_byte = body[nal_header_offset]
        nal_unit_type = (first_byte >> 1) & 0x3F
        units.append(
            CPVNalUnitInfo(
                offset_in_body=match.start(),
                nal_unit_type=nal_unit_type,
                nal_unit_name=hevc_nal_unit_name(nal_unit_type),
            )
        )
    return units


def parse_telemetry_payload(record: CPVRecord, body: bytes) -> CPVTelemetryPayload:
    """Attempt to decode a TELEMETRY-family record's body as JSON.

    Only reports `valid_json=True` when the body actually contains a
    complete, parseable JSON object (`{...}`) — never assumes every
    TELEMETRY-family record carries JSON (evidence showed some
    higher-type-tag variants, e.g. `0x9f1`/`0x19f1`, are binary, not text).

    Args:
        record: The originating `CPVRecord` (must be TELEMETRY family).
        body: The record's already bounded-read body bytes.

    Returns:
        A `CPVTelemetryPayload`. `raw_text` preserves the full body as
        latin-1 text (a byte-preserving, never-raising decode) when no
        JSON object was found, or just the matched JSON substring when one
        was.
    """
    full_text = body.decode("latin1")
    brace_index = full_text.find("{")
    if brace_index == -1:
        return CPVTelemetryPayload(
            record_offset=record.offset,
            type_tag=record.type_tag,
            raw_text=full_text,
            valid_json=False,
            parsed=None,
        )

    decoder = json.JSONDecoder()
    try:
        obj, end_index = decoder.raw_decode(full_text, brace_index)
    except json.JSONDecodeError:
        return CPVTelemetryPayload(
            record_offset=record.offset,
            type_tag=record.type_tag,
            raw_text=full_text,
            valid_json=False,
            parsed=None,
        )

    if not isinstance(obj, dict):
        return CPVTelemetryPayload(
            record_offset=record.offset,
            type_tag=record.type_tag,
            raw_text=full_text,
            valid_json=False,
            parsed=None,
        )

    parsed: dict[str, Any] = obj
    return CPVTelemetryPayload(
        record_offset=record.offset,
        type_tag=record.type_tag,
        raw_text=full_text[brace_index:end_index],
        valid_json=True,
        parsed=parsed,
    )


def parse_cp_plus_export_filename(name: str) -> CPVFilenameInfo | None:
    """Best-effort parse of a CP Plus export filename's channel/stream/timestamps.

    Matches the convention observed on every file in the analyzed evidence
    package (e.g. `NVR_ch1_main_20260828162000_20260828162002.cpv`). This
    is filename-derived provenance only — see `CPVFilenameInfo`'s
    docstring for why it is kept distinct from the binary counter fields.

    Args:
        name: A filename (not a full path).

    Returns:
        A `CPVFilenameInfo`, or `None` if `name` does not match the
        expected pattern at all (never a partially-guessed result).
    """
    match = _EXPORT_FILENAME_RE.match(name)
    if match is None:
        return None
    try:
        # Deliberately naive: the filename encodes no timezone (the case's
        # known device fact sheet says NVR timezone is IST, but that is
        # external, examiner-supplied context, not something this filename
        # itself asserts) — attaching a timezone here would fabricate
        # precision the source data does not contain.
        start = datetime.strptime(match.group("start"), "%Y%m%d%H%M%S")  # noqa: DTZ007
        end = datetime.strptime(match.group("end"), "%Y%m%d%H%M%S")  # noqa: DTZ007
    except ValueError:
        return None
    return CPVFilenameInfo(
        channel=int(match.group("channel")),
        stream_label=match.group("stream"),
        start_original=start,
        end_original=end,
    )


def analyze_cpv_file(
    reader: EvidenceStorageReader, *, telemetry_sample_limit: int = TELEMETRY_SAMPLE_LIMIT
) -> CPVFileAnalysis:
    """Produce a structural summary of one CPV file via one bounded/streaming walk.

    Args:
        reader: An already-open evidence reader.
        telemetry_sample_limit: Maximum number of TELEMETRY-family records
            to fully body-read and decode.

    Returns:
        A `CPVFileAnalysis`. Never raises — truncation/corruption is
        reported via its `truncated`/`corrupted`/`warnings` fields.
    """
    size = reader.size()

    if size < OUTER_HEADER_SIZE:
        return CPVFileAnalysis(
            outer_header=parse_outer_header(reader) if size > 0 else None,
            record_count=0,
            family_histogram={},
            telemetry_samples=(),
            nal_units=(),
            truncated=True,
            corrupted=False,
            bytes_scanned=size,
            container_size=size,
            last_valid_record_end=0,
            warnings=(
                (
                    f"container is {size} byte(s), smaller than the {OUTER_HEADER_SIZE}-byte "
                    "outer header; no records were scanned"
                ),
            ),
        )

    outer_header = parse_outer_header(reader)
    family_histogram: dict[CPVRecordFamily, int] = {}
    telemetry_samples: list[CPVTelemetryPayload] = []
    nal_units: list[CPVNalUnitInfo] = []
    warnings: list[str] = []
    truncated = False
    corrupted = False
    record_count = 0
    last_valid_record_end = OUTER_HEADER_SIZE
    nal_scanned = False

    for record in iter_cpv_records(reader):
        if record.validity == CPVRecordValidity.VALID:
            record_count += 1
            family_histogram[record.family] = family_histogram.get(record.family, 0) + 1
            if record.next_offset is not None:
                last_valid_record_end = record.next_offset

            if not nal_scanned and record.family == CPVRecordFamily.KEYFRAME_MARKER:
                body = read_record_body(reader, record)
                found_units = find_annexb_nal_units(body)
                if found_units:
                    nal_units.extend(found_units)
                    nal_scanned = True

            if (
                record.family == CPVRecordFamily.TELEMETRY
                and len(telemetry_samples) < telemetry_sample_limit
            ):
                body = read_record_body(reader, record)
                telemetry_samples.append(parse_telemetry_payload(record, body))
            continue

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
        # CPVRecordValidity.TRAILING_PADDING: neither truncated nor corrupted —
        # this is the expected end of real records for a padded container.
        break

    return CPVFileAnalysis(
        outer_header=outer_header,
        record_count=record_count,
        family_histogram=family_histogram,
        telemetry_samples=tuple(telemetry_samples),
        nal_units=tuple(nal_units),
        truncated=truncated,
        corrupted=corrupted,
        bytes_scanned=last_valid_record_end,
        container_size=size,
        last_valid_record_end=last_valid_record_end,
        warnings=tuple(warnings),
    )
