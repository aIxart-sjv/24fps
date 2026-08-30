"""Tests for the CP Plus parser (app/adapters/cp_plus/parser.py).

Phase 8 / Fourth Backend Milestone. Covers the parser's honest
UNSUPPORTED/UNKNOWN behavior (no controlled CP Plus fixture exists yet),
bounded/validated reads, determinism, parser-version metadata, and
read-only/source-immutability discipline.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.cp_plus.models import CPPlusParseStatus
from app.adapters.cp_plus.parser import MAX_SINGLE_READ, PARSER_VERSION, CPPlusParser, bounded_read


@pytest.fixture
def sample_evidence(tmp_path: Path) -> Path:
    path = tmp_path / "evidence.bin"
    path.write_bytes(os.urandom(8192))
    return path


# --- validate_structure / enumerate_recordings honesty ---


def test_validate_structure_delegates_to_detector(sample_evidence: Path):
    with FileBackedReader(sample_evidence) as reader:
        parser = CPPlusParser(reader)
        result = parser.validate_structure()
    assert result.status == CPPlusParseStatus.UNSUPPORTED


def test_enumerate_recordings_is_empty_and_honest_without_a_validated_signature(
    sample_evidence: Path,
):
    with FileBackedReader(sample_evidence) as reader:
        parser = CPPlusParser(reader, source_evidence_id="E001")
        result = parser.enumerate_recordings()

    assert result.status == CPPlusParseStatus.UNSUPPORTED
    assert result.recordings == []
    assert result.discovered_count == 0
    assert result.affected_regions == []
    assert result.parser_version == PARSER_VERSION
    assert "none matched this evidence's header" in result.reason


def test_enumerate_recordings_on_undersized_container_is_unknown(tmp_path: Path):
    path = tmp_path / "tiny.bin"
    path.write_bytes(b"\x00" * 10)
    with FileBackedReader(path) as reader:
        result = CPPlusParser(reader).enumerate_recordings()
    assert result.status == CPPlusParseStatus.UNKNOWN
    assert result.recordings == []


def test_identify_storage_regions_is_empty_without_a_validated_layout(sample_evidence: Path):
    with FileBackedReader(sample_evidence) as reader:
        assert CPPlusParser(reader).identify_storage_regions() == []


def test_parser_version_no_longer_carries_the_unvalidated_suffix():
    """PARSER_VERSION dropped "-unvalidated" once a real fixture parsed successfully.

    See app/adapters/cp_plus/parser.py's module docstring: the suffix was
    load-bearing and could only be dropped once this parser actually
    parsed a real, controlled CP Plus fixture (see
    test_cp_plus_real_evidence_integration.py).
    """
    assert "unvalidated" not in PARSER_VERSION


# --- determinism ---


def test_enumerate_recordings_is_deterministic(sample_evidence: Path):
    with FileBackedReader(sample_evidence) as reader:
        parser = CPPlusParser(reader)
        first = parser.enumerate_recordings()
        second = parser.enumerate_recordings()
    assert first == second


# --- bounded_read: offset/length validation ---


def test_bounded_read_rejects_negative_offset(sample_evidence: Path):
    with (
        FileBackedReader(sample_evidence) as reader,
        pytest.raises(ValueError, match="non-negative"),
    ):
        bounded_read(reader, -1, 10)


def test_bounded_read_rejects_negative_length(sample_evidence: Path):
    with (
        FileBackedReader(sample_evidence) as reader,
        pytest.raises(ValueError, match="non-negative"),
    ):
        bounded_read(reader, 0, -1)


def test_bounded_read_rejects_length_over_the_parser_limit(sample_evidence: Path):
    with (
        FileBackedReader(sample_evidence) as reader,
        pytest.raises(ValueError, match="bounded-read limit"),
    ):
        bounded_read(reader, 0, MAX_SINGLE_READ + 1)


def test_bounded_read_rejects_offset_beyond_container_size(sample_evidence: Path):
    with FileBackedReader(sample_evidence) as reader:
        size = reader.size()
        with pytest.raises(ValueError, match="beyond the evidence container size"):
            bounded_read(reader, size + 1, 10)


def test_bounded_read_allows_offset_at_exact_end_of_container(sample_evidence: Path):
    with FileBackedReader(sample_evidence) as reader:
        size = reader.size()
        assert bounded_read(reader, size, 10) == b""


def test_bounded_read_returns_requested_slice(sample_evidence: Path):
    content = sample_evidence.read_bytes()
    with FileBackedReader(sample_evidence) as reader:
        assert bounded_read(reader, 10, 20) == content[10:30]


# --- read-only / source-immutability discipline ---


def test_parsing_never_mutates_the_source_file(sample_evidence: Path):
    content = sample_evidence.read_bytes()
    before_mode = stat.S_IMODE(os.stat(sample_evidence).st_mode)
    before_mtime = os.stat(sample_evidence).st_mtime_ns

    with FileBackedReader(sample_evidence) as reader:
        parser = CPPlusParser(reader, source_evidence_id="E001")
        parser.validate_structure()
        parser.enumerate_recordings()
        parser.identify_storage_regions()

    assert sample_evidence.read_bytes() == content
    assert stat.S_IMODE(os.stat(sample_evidence).st_mode) == before_mode
    assert os.stat(sample_evidence).st_mtime_ns == before_mtime


def test_cp_plus_parser_exposes_no_write_method():
    public_methods = {name for name in dir(CPPlusParser) if not name.startswith("_")}
    assert not any("write" in name for name in public_methods)


# --- truncated / malformed input never crashes the parser ---


def test_zero_byte_evidence_is_handled_without_crashing(tmp_path: Path):
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    with FileBackedReader(path) as reader:
        result = CPPlusParser(reader).enumerate_recordings()
    assert result.status == CPPlusParseStatus.UNKNOWN
    assert result.recordings == []
