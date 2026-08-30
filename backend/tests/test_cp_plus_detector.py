"""Tests for CP Plus structure detection (app/adapters/cp_plus/detector.py).

Phase 8 / Fourth Backend Milestone. `KNOWN_CP_PLUS_SIGNATURES` now holds
one real, evidence-validated signature ("ADIT-v1" — see
app/adapters/cp_plus/models.py's module docstring). These tests exercise
the detector's honest, deterministic UNKNOWN/UNSUPPORTED behavior for
non-matching content, its bounded-read discipline, and (using only the
real, already-validated magic constant, never an invented structure) that
a correct signature is actually recognized. End-to-end validation against
the real 13-file evidence package lives in
test_cp_plus_real_evidence_integration.py.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

from app.acquisition.storage_reader import EvidenceStorageReader, FileBackedReader
from app.adapters.cp_plus.detector import (
    DETECTION_HEADER_WINDOW,
    MINIMUM_INSPECTABLE_SIZE,
    detect_cp_plus_structure,
)
from app.adapters.cp_plus.models import ADIT_MAGIC, OUTER_HEADER_SIZE, CPPlusParseStatus

# --- undersized / degenerate containers -> UNKNOWN ---


def test_empty_container_is_unknown(tmp_path: Path):
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    with FileBackedReader(path) as reader:
        result = detect_cp_plus_structure(reader)
    assert result.status == CPPlusParseStatus.UNKNOWN
    assert result.matched_signature is None
    assert result.evidence_size == 0
    assert result.bytes_inspected == 0


def test_container_below_minimum_size_is_unknown(tmp_path: Path):
    path = tmp_path / "tiny.bin"
    path.write_bytes(os.urandom(MINIMUM_INSPECTABLE_SIZE - 1))
    with FileBackedReader(path) as reader:
        result = detect_cp_plus_structure(reader)
    assert result.status == CPPlusParseStatus.UNKNOWN
    assert "smaller than" in result.reason


def test_container_at_exact_minimum_size_is_not_unknown_for_size_reasons(tmp_path: Path):
    path = tmp_path / "min.bin"
    path.write_bytes(os.urandom(MINIMUM_INSPECTABLE_SIZE))
    with FileBackedReader(path) as reader:
        result = detect_cp_plus_structure(reader)
    # MINIMUM_INSPECTABLE_SIZE (512) is still smaller than the ADIT-v1
    # signature's own minimum_container_size (1024), so random bytes at
    # exactly 512 resolve to UNSUPPORTED — but for a different,
    # distinguishable reason than the "too small to inspect" UNKNOWN case
    # above.
    assert result.status == CPPlusParseStatus.UNSUPPORTED


# --- well-formed-enough but unrecognized content -> UNSUPPORTED, never a guess ---


@pytest.mark.parametrize(
    "content",
    [
        b"\x00" * 8192,
        b"\xff" * 8192,
        os.urandom(8192),
        b"DAHUA" + os.urandom(8000),  # a plausible-looking but unvalidated label
        b"CPPLUS" + os.urandom(8000),  # must not be treated as a signature match
    ],
)
def test_no_content_is_ever_reported_as_supported(tmp_path: Path, content: bytes):
    """Detection never guesses: content that doesn't match ADIT-v1 is always UNSUPPORTED."""
    path = tmp_path / "sample.bin"
    path.write_bytes(content)
    with FileBackedReader(path) as reader:
        result = detect_cp_plus_structure(reader)
    assert result.status == CPPlusParseStatus.UNSUPPORTED
    assert result.matched_signature is None
    assert "none matched this evidence's header" in result.reason


def test_unsupported_result_cites_the_registered_signature_label(tmp_path: Path):
    path = tmp_path / "sample.bin"
    path.write_bytes(os.urandom(4096))
    with FileBackedReader(path) as reader:
        result = detect_cp_plus_structure(reader)
    assert "1 validated CP Plus signature" in result.reason
    assert "ADIT-v1" in result.reason


# --- positive match, using only the real, already-validated magic constant ---


def test_adit_v1_magic_at_offset_zero_is_recognized(tmp_path: Path):
    """A minimal synthetic container using the real ADIT-v1 magic must be recognized.

    This uses ONLY the magic bytes established from real evidence
    (app.adapters.cp_plus.models.ADIT_MAGIC) — it does not invent any CP
    Plus structure. End-to-end validation against the real 13-file
    evidence package lives in test_cp_plus_real_evidence_integration.py.
    """
    path = tmp_path / "adit.bin"
    header = ADIT_MAGIC + struct.pack("<II", 0, 0) + b"\x00" * (OUTER_HEADER_SIZE - 16)
    path.write_bytes(header)
    with FileBackedReader(path) as reader:
        result = detect_cp_plus_structure(reader)
    assert result.status == CPPlusParseStatus.SUPPORTED_VALID
    assert result.matched_signature == "ADIT-v1"


def test_adit_v1_magic_below_minimum_container_size_is_unsupported(tmp_path: Path):
    """The signature requires >= OUTER_HEADER_SIZE bytes even with a correct magic."""
    path = tmp_path / "adit_short.bin"
    path.write_bytes(ADIT_MAGIC + b"\x00" * 512)
    with FileBackedReader(path) as reader:
        result = detect_cp_plus_structure(reader)
    assert result.status == CPPlusParseStatus.UNSUPPORTED


# --- determinism ---


def test_detection_is_deterministic(tmp_path: Path):
    path = tmp_path / "sample.bin"
    path.write_bytes(os.urandom(4096))
    with FileBackedReader(path) as reader:
        first = detect_cp_plus_structure(reader)
        second = detect_cp_plus_structure(reader)
    assert first == second


# --- bounded reads ---


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


def test_detection_never_reads_more_than_the_bounded_header_window(tmp_path: Path):
    """A single identification pass must never approach a whole-container read.

    Uses a large *sparse* file (created via truncate, so it consumes ~0
    actual disk blocks) purely to prove the read-size bound holds
    regardless of container size — this is a framework-mechanics test, not
    a claim about real CP Plus evidence size.
    """
    path = tmp_path / "large_sparse.dd"
    large_size = 4 * 1024 * 1024 * 1024  # 4 GiB, logical size only
    with path.open("wb") as handle:
        handle.truncate(large_size)

    inner = FileBackedReader(path)
    wrapped = _RecordingReader(inner)
    try:
        assert wrapped.size() == large_size
        result = detect_cp_plus_structure(wrapped)
    finally:
        wrapped.close()

    assert result.evidence_size == large_size
    assert wrapped.read_calls, "detection must read at least the header"
    assert all(length <= DETECTION_HEADER_WINDOW for _offset, length in wrapped.read_calls)
    assert sum(length for _offset, length in wrapped.read_calls) <= DETECTION_HEADER_WINDOW


# --- unreadable evidence -> controlled result, never a crash ---


class _ExplodingReader(EvidenceStorageReader):
    """A reader whose read() always fails, simulating unreadable/bad-sector media."""

    def __init__(self, size: int) -> None:
        self._size = size
        self.sector_size = 512

    def read(self, offset: int, length: int) -> bytes:
        raise OSError("simulated bad sector")

    def size(self) -> int:
        return self._size

    def metadata(self) -> dict[str, object]:
        return {"format": "simulated"}

    def hash(self) -> dict[str, str] | None:
        return None

    def close(self) -> None:
        pass


def test_read_error_during_detection_is_a_controlled_result_not_a_crash():
    reader = _ExplodingReader(size=8192)
    result = detect_cp_plus_structure(reader)
    assert result.status == CPPlusParseStatus.UNKNOWN
    assert result.warnings
    assert "simulated bad sector" in result.warnings[0]
