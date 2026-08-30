"""
Acquisition domain — read-only access to acquired forensic evidence.
Master Specification Section 89, Phase 5: "Acquisition abstraction: storage
reader, RAW/DD, E01/libewf, native export registration, platform
abstraction."

`open_reader` is the single dispatch point from an already-registered
Evidence item's declared `source_type` to the concrete
`EvidenceStorageReader` that can read it. It is deliberately dumb: it
trusts the examiner-declared `source_type`, it never inspects file bytes to
guess the format — byte-signature-based format detection is Phase 6
("Device/format identification"), layered on top of this module, not
inside it.
"""

from __future__ import annotations

from pathlib import Path

from app.acquisition.e01_handler import (
    E01FormatError,
    E01Reader,
    E01UnavailableError,
    is_e01_support_available,
)
from app.acquisition.raw_imager import RawDDReader
from app.acquisition.storage_reader import (
    DEFAULT_SECTOR_SIZE,
    EvidenceStorageReader,
    FileBackedReader,
)

__all__ = [
    "DEFAULT_SECTOR_SIZE",
    "E01FormatError",
    "E01Reader",
    "E01UnavailableError",
    "EvidenceStorageReader",
    "FileBackedReader",
    "RawDDReader",
    "is_e01_support_available",
    "open_reader",
]

_RAW_DD_SOURCE_TYPES = frozenset({"raw_dd", "direct_storage"})
_E01_SOURCE_TYPES = frozenset({"e01"})


def open_reader(
    source_type: str, source_path: Path, *, sector_size: int = DEFAULT_SECTOR_SIZE
) -> EvidenceStorageReader:
    """Open the appropriate read-only reader for a registered evidence source.

    Args:
        source_type: The evidence's declared `source_type` (e.g.
            `"e01"`, `"raw_dd"`, `"native_export"`).
        source_path: Resolved path to the evidence source. Must be an
            existing regular file — directory-based exports are not opened
            through this single-stream interface (their contents are
            enumerated file-by-file, which is later-phase scope).
        sector_size: Sector size to use for formats where it matters
            (ignored by E01, which reports its own).

    Returns:
        An open `EvidenceStorageReader` positioned at the start of the
        evidence. Callers are responsible for calling `close()` (or using
        it as a context manager).

    Raises:
        ValueError: If `source_path` is not an existing regular file.
        E01UnavailableError: If `source_type` is `"e01"` and `pyewf` is not
            installed.
        E01FormatError: If `source_type` is `"e01"` and the file does not
            carry a valid EWF/E01 signature.
    """
    if source_path.is_dir():
        raise ValueError(
            f"{source_path} is a directory; directory-based exports are not opened through "
            "the single-stream EvidenceStorageReader interface"
        )

    if source_type in _E01_SOURCE_TYPES:
        return E01Reader(source_path)
    if source_type in _RAW_DD_SOURCE_TYPES:
        return RawDDReader(source_path, sector_size=sector_size)
    return FileBackedReader(
        source_path, sector_size=sector_size, format_label=source_type or "file"
    )
