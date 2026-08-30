"""Real CP Plus evidence — Phase 8 acceptance test.

This is the integration test the Phase 8 task explicitly requires: proof,
against the real 13-file evidence package (never synthetic bytes), that:

  1. all 13 files are recognized as CPV ("ADIT-v1"),
  2. the session relationship (one continuous recording) is correctly
     identified,
  3. record parsing succeeds for valid records,
  4. H.265 payloads are detected,
  5. telemetry records are identified,
  6. no evidence file is modified by any of the above, and
  7. the parser completes without consuming the entire dataset into memory.

All tests here are `requires_real_evidence`-marked and skip (not fail)
when the out-of-repo evidence package is absent. Granular unit-level
coverage of the underlying logic lives in test_cp_plus_container.py and
test_cp_plus_session.py; this file is deliberately the end-to-end proof.
"""

from __future__ import annotations

from app.acquisition.storage_reader import EvidenceStorageReader, FileBackedReader
from app.adapters.cp_plus.container import (
    MAX_RECORD_BODY_READ,
    analyze_cpv_file,
    parse_outer_header,
)
from app.adapters.cp_plus.detector import detect_cp_plus_structure
from app.adapters.cp_plus.models import CPPlusParseStatus, CPVSessionLinkStatus, CPVTimestampStatus
from app.adapters.cp_plus.parser import CPPlusParser
from app.adapters.cp_plus.session import link_cpv_session, segment_descriptor_from_header
from tests.fixtures.cp_plus_evidence import (
    EVIDENCE_DIR,
    load_expected_sha256,
    real_cpv_paths,
    requires_real_evidence,
    sha256_of,
)

_RECOGNIZED_STATUSES = frozenset(
    {
        CPPlusParseStatus.SUPPORTED_VALID,
        CPPlusParseStatus.SUPPORTED_PARTIAL,
        CPPlusParseStatus.SUPPORTED_CORRUPTED,
    }
)


class _RecordingReader(EvidenceStorageReader):
    """Wraps a real reader, recording every (offset, length) passed to read()."""

    def __init__(self, inner: EvidenceStorageReader) -> None:
        self._inner = inner
        self.read_calls: list[tuple[int, int]] = []
        self.sector_size = inner.sector_size

    def read(self, offset: int, length: int) -> bytes:
        self.read_calls.append((offset, length))
        return self._inner.read(offset, length)

    def size(self) -> int:
        return self._inner.size()

    def metadata(self) -> dict[str, object]:
        return self._inner.metadata()

    def hash(self) -> dict[str, str] | None:
        return self._inner.hash()

    def close(self) -> None:
        self._inner.close()


@requires_real_evidence
def test_acceptance_all_13_files_recognized_session_linked_hevc_and_telemetry_found_no_mutation():
    """The single consolidated acceptance test the Phase 8 task asks for."""
    paths = real_cpv_paths()
    assert len(paths) == 13, "expected exactly 13 real .cpv files in the evidence package"

    expected_hashes = load_expected_sha256()
    pre_hashes = {path.name: sha256_of(path) for path in paths}
    for name, digest in pre_hashes.items():
        assert (
            expected_hashes[name] == digest
        ), f"{name} does not match SHA256SUMS.txt before the test ran"

    # --- 1. all 13 files are recognized as CPV ---
    descriptors = []
    any_hevc_found = False
    any_telemetry_found = False
    for path in paths:
        with FileBackedReader(path) as reader:
            parser = CPPlusParser(reader, source_evidence_id=path.name)
            detection = parser.validate_structure()
            assert (
                detection.status == CPPlusParseStatus.SUPPORTED_VALID
            ), f"{path.name} was not recognized as ADIT-v1: {detection.reason}"
            assert detection.matched_signature == "ADIT-v1"

            # --- 3. record parsing succeeds for valid records ---
            enumeration = parser.enumerate_recordings()
            assert enumeration.status in _RECOGNIZED_STATUSES
            assert enumeration.discovered_count == 1
            recording = enumeration.recordings[0]

            # --- timestamp preservation without incorrect conversion ---
            assert recording.timestamp_status == CPVTimestampStatus.RAW_COUNTER_UNVALIDATED
            assert recording.raw_timestamp is not None
            assert recording.timestamp_source == "cpv_outer_header_offset_8"
            assert "NOT a validated real-world timestamp" in (
                recording.timestamp_interpretation or ""
            )

            analysis = recording.analysis
            assert analysis is not None
            assert analysis.record_count > 0

            if any(u.nal_unit_name in ("VPS", "SPS", "PPS") for u in analysis.nal_units):
                any_hevc_found = True
            if any(t.valid_json for t in analysis.telemetry_samples):
                any_telemetry_found = True

            header = parse_outer_header(reader)
        descriptors.append(segment_descriptor_from_header(path.name, header))

    # --- 4. H.265 payloads are detected (at least somewhere across the session) ---
    assert any_hevc_found, "no VPS/SPS/PPS NAL unit was found in any of the 13 real files"

    # --- 5. telemetry records are identified ---
    assert (
        any_telemetry_found
    ), "no valid JSON telemetry record was found in any of the 13 real files"

    # --- 2. the session relationship is correctly identified ---
    assert all(d.readable for d in descriptors)
    session = link_cpv_session(descriptors)
    assert session.overall_status == CPVSessionLinkStatus.CONTINUOUS
    assert len(session.links) == 12

    # --- 6. no evidence file was modified ---
    post_hashes = {path.name: sha256_of(path) for path in paths}
    assert post_hashes == pre_hashes


@requires_real_evidence
def test_acceptance_parsing_never_loads_the_largest_file_wholesale():
    """The parser completes without consuming the entire dataset into memory.

    Uses the largest real segment (~59 MB) and asserts no single `read()`
    call requested anywhere close to the file's full size, and none
    exceeded this parser's documented per-record bound.
    """
    paths = real_cpv_paths()
    largest = max(paths, key=lambda p: p.stat().st_size)
    size = largest.stat().st_size
    assert size > 10 * 1024 * 1024  # sanity: this really is one of the large segments

    inner = FileBackedReader(largest)
    wrapped = _RecordingReader(inner)
    try:
        analysis = analyze_cpv_file(wrapped)
    finally:
        wrapped.close()

    assert analysis.record_count > 1000
    assert wrapped.read_calls
    assert all(length <= MAX_RECORD_BODY_READ for _offset, length in wrapped.read_calls)
    # No single read approached the file's own size — the strongest direct
    # evidence this was a streaming walk, not a whole-file load.
    assert all(length < size // 4 for _offset, length in wrapped.read_calls)


@requires_real_evidence
def test_acceptance_cpv_player_exe_is_a_real_unsupported_file():
    """A real, non-fabricated UNSUPPORTED case: the vendor player is not a CPV container."""
    player_path = EVIDENCE_DIR / "CPV Player.exe"
    assert player_path.is_file()
    with FileBackedReader(player_path) as reader:
        detection = detect_cp_plus_structure(reader)
    assert detection.status == CPPlusParseStatus.UNSUPPORTED
    assert detection.matched_signature is None
