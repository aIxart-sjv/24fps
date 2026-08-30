"""Tests for generic bounded-read carving (app/recovery/carving.py), Phase 10."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.acquisition.storage_reader import FileBackedReader
from app.recovery.carving import carve_by_signature


def _write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_carving_finds_non_overlapping_signatures(tmp_path: Path):
    sig = b"CPAV"
    data = bytearray(b"\x00" * 2000)
    positions = [0, 10, 500, 1996]
    for p in positions:
        data[p : p + 4] = sig
    path = _write(tmp_path, "test.bin", bytes(data))

    with FileBackedReader(path) as reader:
        found = list(carve_by_signature(reader, sig, chunk_size=1000))
    assert found == positions


def test_carving_finds_signature_straddling_a_chunk_boundary(tmp_path: Path):
    sig = b"CPAV"
    data = bytearray(b"\x00" * 2000)
    # placed to straddle the 1000-byte chunk boundary exactly
    data[997:1001] = sig
    path = _write(tmp_path, "straddle.bin", bytes(data))

    with FileBackedReader(path) as reader:
        found = list(carve_by_signature(reader, sig, chunk_size=1000))
    assert found == [997]


def test_carving_with_tiny_chunk_size_still_finds_every_match(tmp_path: Path):
    sig = b"CPAV"
    data = bytearray(b"\x00" * 200)
    positions = [0, 10, 50, 97, 150, 196]
    for p in positions:
        data[p : p + 4] = sig
    path = _write(tmp_path, "tiny_chunks.bin", bytes(data))

    with FileBackedReader(path) as reader:
        found = list(carve_by_signature(reader, sig, chunk_size=8))
    assert found == positions


def test_carving_on_empty_file_finds_nothing(tmp_path: Path):
    path = _write(tmp_path, "empty.bin", b"")
    with FileBackedReader(path) as reader:
        assert list(carve_by_signature(reader, b"CPAV")) == []


def test_carving_with_no_matches_finds_nothing(tmp_path: Path):
    path = _write(tmp_path, "no_match.bin", b"\x00" * 5000)
    with FileBackedReader(path) as reader:
        assert list(carve_by_signature(reader, b"CPAV", chunk_size=1000)) == []


def test_carving_never_reads_more_than_chunk_size_plus_overlap(tmp_path: Path):
    sig = b"CPAV"
    path = _write(tmp_path, "big.bin", b"\x00" * 100_000)

    read_sizes: list[int] = []
    real_reader = FileBackedReader(path)
    original_read = real_reader.read

    def _tracking_read(offset: int, length: int) -> bytes:
        read_sizes.append(length)
        return original_read(offset, length)

    real_reader.read = _tracking_read  # type: ignore[method-assign]
    try:
        list(carve_by_signature(real_reader, sig, chunk_size=4096))
    finally:
        real_reader.close()

    assert read_sizes
    assert all(size <= 4096 for size in read_sizes)


def test_carving_rejects_empty_signature(tmp_path: Path):
    path = _write(tmp_path, "x.bin", b"data")
    with FileBackedReader(path) as reader, pytest.raises(ValueError, match="signature"):
        list(carve_by_signature(reader, b""))


def test_carving_rejects_chunk_size_smaller_than_signature(tmp_path: Path):
    path = _write(tmp_path, "x.bin", b"data")
    with FileBackedReader(path) as reader, pytest.raises(ValueError, match="chunk_size"):
        list(carve_by_signature(reader, b"CPAV", chunk_size=2))
