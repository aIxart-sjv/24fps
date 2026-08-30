"""
Generic, bounded-read file/frame carving.
Master Specification Section 23 ("File Carving"): "carving results are
candidates; context must be reconstructed if possible; confidence should
reflect uncertainty. Never present a carved candidate as an unquestionable
original recording." Section 60 (large-evidence safety): never load an
entire multi-terabyte image into memory.

This module is deliberately vendor-agnostic: it knows nothing about CPV,
DHAV, or any other container format — it only knows how to scan an
`EvidenceStorageReader` for a byte signature using bounded, overlap-safe
chunked reads. Vendor-specific interpretation of what a found offset means
(e.g. "this is a CPAV record start") belongs in the vendor's own
`app/adapters/<vendor>/recovery.py`, which hands each candidate offset to
that vendor's *existing* record parser to validate — carving never
reimplements format parsing itself (Tech Stack Section 6: "FFmpeg/carving
does NOT solve proprietary DVR filesystem parsing").
"""

from __future__ import annotations

from collections.abc import Iterator

from app.acquisition.storage_reader import EvidenceStorageReader

#: Default chunk size for a carving scan. Generous enough to make a
#: multi-gigabyte scan fast, small enough that no single read approaches
#: "load the whole image" territory (Master Specification Section 60).
DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024


def carve_by_signature(
    reader: EvidenceStorageReader,
    signature: bytes,
    *,
    start_offset: int = 0,
    end_offset: int | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[int]:
    """Scan `reader` for every occurrence of `signature`, via bounded reads.

    Reads `chunk_size`-sized, overlapping windows (each overlapping the
    previous by `len(signature) - 1` bytes) so a signature that straddles a
    chunk boundary is never missed, without ever holding more than one
    chunk in memory at a time.

    Args:
        reader: An already-open evidence reader.
        signature: The exact byte sequence to search for. Must be
            non-empty.
        start_offset: Byte offset to begin scanning from.
        end_offset: Byte offset to stop scanning at (exclusive). `None`
            (the default) scans to the end of the container.
        chunk_size: Bytes read per scan window. Must be at least as large
            as `signature`.

    Yields:
        Every absolute byte offset at which `signature` occurs, in
        ascending order. Overlapping/adjacent matches are all reported
        (never deduplicated or merged) — interpreting which candidates are
        meaningful is the caller's job.

    Raises:
        ValueError: If `signature` is empty, `chunk_size` is smaller than
            `signature`, or `start_offset`/`end_offset` is invalid.
    """
    if not signature:
        raise ValueError("signature must be non-empty")
    if chunk_size < len(signature):
        raise ValueError("chunk_size must be at least as large as signature")
    if start_offset < 0:
        raise ValueError("start_offset must be non-negative")

    size = reader.size()
    scan_end = size if end_offset is None else min(end_offset, size)
    if scan_end <= start_offset:
        return

    overlap = len(signature) - 1
    offset = start_offset
    last_reported_end = -1  # exclusive end of the last window already scanned

    while offset < scan_end:
        read_length = min(chunk_size, scan_end - offset)
        window = reader.read(offset, read_length)
        if not window:
            break

        search_start = 0
        while True:
            match_index = window.find(signature, search_start)
            if match_index == -1:
                break
            absolute_offset = offset + match_index
            if absolute_offset > last_reported_end:
                yield absolute_offset
                last_reported_end = absolute_offset
            search_start = match_index + 1

        if len(window) < read_length:
            break  # end of container reached mid-window

        advance = read_length - overlap if read_length > overlap else read_length
        offset += advance
