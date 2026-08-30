"""
RAW/DD forensic image reading.
Master Specification Section 12 ("Forensic Image Handling"): "RAW/DD: treat
as exact source representation, support sector-oriented reading, allow
random access to sectors, calculate hashes, preserve acquisition metadata
separately."

STATUS: This module currently provides the RAW/DD *reader* only — importing
an already-acquired RAW/DD image through the common
`app.acquisition.storage_reader.EvidenceStorageReader` interface (Phase 5,
Master Specification Section 89, Path 3: "import RAW/DD"). Creating a new
RAW/DD image from a live device (Path 2: "Direct storage acquisition") is
acquisition-hardware work that depends on `app.acquisition.interface`
(`StorageAccess`) having a real platform implementation, which remains
deferred — see `linux_storage.py`/`windows_storage.py`. When that lands,
the imaging half of this module can be added here without disturbing the
reader below.
"""

from __future__ import annotations

from pathlib import Path

from app.acquisition.storage_reader import DEFAULT_SECTOR_SIZE, FileBackedReader


class RawDDReader(FileBackedReader):
    """Read-only, sector-aware reader for a RAW/DD forensic image file.

    A RAW/DD image is a bit-for-bit copy of the source storage with no
    container header, so reading it is byte-identical to reading any other
    file — this subclass exists to give it its own type/format identity
    (`metadata()["format"] == "raw_dd"`) distinct from a generic exported
    file, as the master specification treats them as conceptually separate
    evidence types (Section 8).
    """

    def __init__(self, path: Path, *, sector_size: int = DEFAULT_SECTOR_SIZE) -> None:
        """Open a RAW/DD image file for read-only, sector-oriented reading.

        Args:
            path: Path to the RAW/DD image file.
            sector_size: Sector size of the source media, in bytes.

        Raises:
            ValueError: If `path` does not resolve to an existing regular
                file, or `sector_size` is not positive.
        """
        super().__init__(path, sector_size=sector_size, format_label="raw_dd")
