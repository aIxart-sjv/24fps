"""
E01/EWF forensic image reading.
Master Specification Section 12 ("Forensic Image Handling"): "E01: use
libewf, import/read the image, expose a common storage reader interface to
the parsing engine." Tech Stack Section 2: "We absolutely should not
implement E01 ourselves" — all EWF container parsing is delegated to the
`libewf-python` (`pyewf`) bindings around the libyal `libewf` library.

`pyewf` is treated as an optional runtime dependency. If it is not
importable, `E01Reader` raises `E01UnavailableError` immediately rather than
falling back to any other interpretation of the file — an unreadable E01
must fail clearly, never be silently misread as a different format (Master
Specification Section 55: "Do NOT... silently map to a wrong vendor").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.acquisition.storage_reader import DEFAULT_SECTOR_SIZE, EvidenceStorageReader

try:
    import pyewf
except ImportError:  # pragma: no cover - exercised only when pyewf is absent
    pyewf = None


class E01UnavailableError(RuntimeError):
    """Raised when E01/EWF support is requested but `pyewf` is not installed."""


class E01FormatError(ValueError):
    """Raised when a file does not carry a valid EWF/E01 signature."""


def is_e01_support_available() -> bool:
    """Return whether the `pyewf` (libewf) bindings are importable.

    Returns:
        True if E01/EWF evidence can be opened in this environment.
    """
    return pyewf is not None


class E01Reader(EvidenceStorageReader):
    """Read-only reader for an E01/EWF forensic image, backed by `pyewf`.

    Supports segmented EWF sets (`.E01`, `.E02`, ...) by globbing every
    segment belonging to the file passed in, matching how libewf itself
    expects a segmented image to be opened.
    """

    def __init__(self, path: Path) -> None:
        """Open an E01/EWF image for read-only access.

        Args:
            path: Path to any one segment of the EWF image (e.g. the
                `.E01` file; later segments are located automatically).

        Raises:
            E01UnavailableError: If `pyewf` is not installed.
            ValueError: If `path` does not resolve to an existing regular
                file.
            E01FormatError: If the file does not carry a valid EWF/E01
                signature.
        """
        if pyewf is None:
            raise E01UnavailableError(
                "E01/EWF support requires the 'libewf-python' (pyewf) package, which is not "
                "installed in this environment. Install it to import E01 evidence; RAW/DD and "
                "native-export evidence remain fully supported without it."
            )

        try:
            resolved = path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"source path does not exist or cannot be resolved: {path}") from exc
        if not resolved.is_file():
            raise ValueError(f"source path must be an existing regular file: {resolved}")

        try:
            segment_files = pyewf.glob(str(resolved))
        except OSError:
            segment_files = []
        if not segment_files:
            segment_files = [str(resolved)]

        if not pyewf.check_file_signature(segment_files[0]):
            raise E01FormatError(f"{resolved} does not have a valid EWF/E01 signature")

        self._path = resolved
        self._handle = pyewf.handle()
        try:
            self._handle.open(segment_files)
        except OSError as exc:
            raise E01FormatError(
                f"{resolved} could not be opened as an EWF/E01 image: {exc}"
            ) from exc
        self._closed = False
        self.sector_size = self._handle.get_bytes_per_sector() or DEFAULT_SECTOR_SIZE

    def read(self, offset: int, length: int) -> bytes:
        if self._closed:
            raise ValueError("reader is closed")
        if offset < 0 or length < 0:
            raise ValueError("offset and length must be non-negative")
        if length == 0:
            return b""
        media_size = self.size()
        if offset >= media_size:
            return b""
        clamped_length = min(length, media_size - offset)
        result: bytes = self._handle.read_buffer_at_offset(clamped_length, offset)
        return result

    def size(self) -> int:
        return int(self._handle.get_media_size())

    def metadata(self) -> dict[str, Any]:
        return {
            "format": "e01",
            "size_bytes": self.size(),
            "sector_size": self.sector_size,
            "source_path": str(self._path),
            "number_of_sectors": self._handle.get_number_of_sectors(),
            "media_type": self._handle.get_media_type(),
            "media_flags": self._handle.get_media_flags(),
            "compression_method": self._handle.get_compression_method(),
            "acquisition_tool_metadata": dict(self._handle.get_header_values()),
        }

    def hash(self) -> dict[str, str] | None:
        values = self._handle.get_hash_values()
        return dict(values) if values else None

    def close(self) -> None:
        if not self._closed:
            self._handle.close()
            self._closed = True
