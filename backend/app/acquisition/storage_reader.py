"""
Generic forensic storage-reading abstraction.
Master Specification Section 12 ("Forensic Image Handling") and the
"Second Backend Milestone" (Section 91): a common, read-only interface so
the parsing engine "does not care whether it is reading: physical HDD,
RAW/DD, E01" — it sees one abstraction regardless of container format.

This is intentionally a different contract from `app.acquisition.interface`
(`StorageAccess`): that interface is for reading a *live* OS storage device
during acquisition (Section 11, "Platform Storage Access"). This module is
for reading an *already-acquired* evidence container (a plain file, a
RAW/DD image, or an E01 image) once it has been registered as evidence.
Nothing here is vendor- or format-aware beyond the container level, so it
stays reusable, unmodified, by Phase 6 device/format identification and
Phase 7+ vendor adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import Any, Self

DEFAULT_SECTOR_SIZE = 512


class EvidenceStorageReader(ABC):
    """Read-only, random-access interface onto an acquired evidence container.

    Every concrete implementation must guarantee it never writes to the
    underlying container — this mirrors the same read-only invariant
    `StorageAccess` guarantees for live devices (Master Specification
    Section 76, rule 1: "Original evidence must be treated as
    immutable/read-only").
    """

    sector_size: int = DEFAULT_SECTOR_SIZE

    @abstractmethod
    def read(self, offset: int, length: int) -> bytes:
        """Read up to `length` bytes starting at `offset`.

        Args:
            offset: Zero-based byte offset to begin reading from.
            length: Maximum number of bytes to read.

        Returns:
            The bytes read. Shorter than `length` only at end-of-container,
            matching standard file-read semantics — this is not an error.

        Raises:
            ValueError: If `offset` or `length` is negative, or the reader
                is closed.
        """
        raise NotImplementedError

    @abstractmethod
    def size(self) -> int:
        """Return the total size in bytes of the evidence container.

        Returns:
            Total size in bytes.
        """
        raise NotImplementedError

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Return what this reader can determine about the container.

        Only information the reader can actually establish is included
        (Master Specification Section 6: "If a value cannot be reliably
        determined, record an explicit unavailable state. Do not guess.").
        This never includes vendor/device identification — that is Phase 6
        scope, layered on top of this reader, not inside it.

        Returns:
            A JSON-serializable metadata dict.
        """
        raise NotImplementedError

    @abstractmethod
    def hash(self) -> dict[str, str] | None:
        """Return hash values embedded in the container itself, if any.

        This is provenance the container format already carries (e.g. an
        E01 image records the acquiring tool's SHA-256/MD5 of the logical
        media). It is never computed here — computing a fresh digest of the
        evidence is a distinct, explicit operation (see
        `app.hashing`/`app.integrity`), not an implicit side effect of
        opening a reader.

        Returns:
            A mapping of algorithm name to lowercase hex digest, or `None`
            if the container carries no embedded hash values.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by this reader.

        Safe to call more than once.
        """
        raise NotImplementedError

    def read_sector(self, sector_number: int) -> bytes:
        """Read one sector, using this reader's `sector_size`.

        Args:
            sector_number: Zero-based sector index.

        Returns:
            The sector's bytes (may be shorter than `sector_size` only at
            end-of-container).

        Raises:
            ValueError: If `sector_number` is negative.
        """
        if sector_number < 0:
            raise ValueError("sector_number must be non-negative")
        return self.read(sector_number * self.sector_size, self.sector_size)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class FileBackedReader(EvidenceStorageReader):
    """Generic read-only reader for any regular file.

    Used directly for native exports and other plain-file evidence, and as
    the base implementation for `RawDDReader` (Master Specification
    Section 91: "file-backed reader" / "raw-image reader" share the same
    underlying mechanics — a RAW/DD image is, at the byte level, an
    ordinary file).
    """

    def __init__(
        self, path: Path, *, sector_size: int = DEFAULT_SECTOR_SIZE, format_label: str = "file"
    ) -> None:
        """Open a file for read-only, random-access reading.

        Args:
            path: Path to the file to read.
            sector_size: Sector size to use for `read_sector`.
            format_label: Format identifier surfaced in `metadata()`.

        Raises:
            ValueError: If `path` does not resolve to an existing regular
                file, or `sector_size` is not positive.
        """
        if sector_size <= 0:
            raise ValueError("sector_size must be positive")

        try:
            resolved = path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"source path does not exist or cannot be resolved: {path}") from exc
        if not resolved.is_file():
            raise ValueError(f"source path must be an existing regular file: {resolved}")

        self._path = resolved
        self._size = resolved.stat().st_size
        self._handle = resolved.open("rb")
        self._format_label = format_label
        self._closed = False
        self.sector_size = sector_size

    def read(self, offset: int, length: int) -> bytes:
        if self._closed:
            raise ValueError("reader is closed")
        if offset < 0 or length < 0:
            raise ValueError("offset and length must be non-negative")
        if length == 0:
            return b""
        self._handle.seek(offset)
        return self._handle.read(length)

    def size(self) -> int:
        return self._size

    def metadata(self) -> dict[str, Any]:
        return {
            "format": self._format_label,
            "size_bytes": self._size,
            "sector_size": self.sector_size,
            "source_path": str(self._path),
        }

    def hash(self) -> dict[str, str] | None:
        return None

    def close(self) -> None:
        if not self._closed:
            self._handle.close()
            self._closed = True
