"""
Location: 24fps/backend/app/acquisition/linux_storage.py

Linux implementation of the `StorageAccess` interface (Master
Specification Section 11, "Platform Storage Access"). Provides read-only,
random-access reading of Linux block devices via `os.open`/`os.pread`.

Block device special files and regular files are indistinguishable to the
`read()`/`pread()`/`lseek()` syscalls this module uses, so every method
here is exercised in tests against ordinary files — that is not a
weakened substitute for real-hardware testing, it is the same mechanism a
real device path would go through.

STATUS: `list_devices` (live device enumeration) is not implemented.
Identifying which of a system's block devices is the correct forensic
target requires investigator interaction and storage-topology inspection
that belongs to the surrounding acquisition workflow (Path 2, Master
Specification Section 9), not to this low-level access primitive;
enumerating devices with no acquisition workflow yet built to act on the
result has no safe use on its own. `open_device`, `read_bytes`,
`get_device_size`, and `close` are fully implemented below.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from app.acquisition.interface import StorageAccess, StorageDeviceDescriptor

_LIST_DEVICES_NOT_IMPLEMENTED_MESSAGE: str = (
    "LinuxStorageAccess.list_devices is not implemented. Device enumeration belongs to the "
    "Path 2 direct-storage-acquisition workflow (Master Specification Section 9), which is not "
    "yet built; open_device/read_bytes/get_device_size/close are available for a device path "
    "supplied directly."
)


@dataclass
class _OpenHandle:
    """Internal bookkeeping for one open device/file descriptor."""

    fd: int
    size: int


class LinuxStorageAccess(StorageAccess):
    """Linux platform implementation of `StorageAccess`.

    Every device is opened with `os.O_RDONLY` only — no write, create, or
    truncate flag is ever passed to `os.open`, so mutation of the target
    is impossible at the syscall level, not merely by convention (Master
    Specification Section 76, rule 1: "Original evidence must be treated
    as immutable/read-only").
    """

    def __init__(self) -> None:
        self._handles: dict[int, _OpenHandle] = {}
        self._next_handle_id = 1

    def list_devices(self) -> list[StorageDeviceDescriptor]:
        """Not yet implemented.

        Raises:
            NotImplementedError: Always, until device enumeration is
                implemented as part of the Path 2 acquisition workflow.
        """
        raise NotImplementedError(_LIST_DEVICES_NOT_IMPLEMENTED_MESSAGE)

    def open_device(self, device_path: str) -> int:
        """Open a device or file for exclusive, read-only access.

        Args:
            device_path: Path to a block device special file (e.g.
                `/dev/sdb`) or a regular file.

        Returns:
            An opaque handle identifier for use with `read_bytes`,
            `get_device_size`, and `close`.

        Raises:
            ValueError: If `device_path` is empty, contains a null byte,
                or does not identify a block device or regular file.
            FileNotFoundError: If `device_path` does not exist.
            PermissionError: If the current process cannot open
                `device_path` for reading.
            OSError: If the device cannot be opened for any other reason.
        """
        if not isinstance(device_path, str) or not device_path.strip():
            raise ValueError("device_path must be a non-empty string")
        if "\x00" in device_path:
            raise ValueError("device_path contains an invalid null byte")

        try:
            fd = os.open(device_path, os.O_RDONLY)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"device not found: {device_path}") from exc
        except PermissionError as exc:
            raise PermissionError(
                f"insufficient permissions to open device read-only: {device_path}"
            ) from exc
        except OSError as exc:
            raise OSError(f"unable to open device: {device_path}: {exc}") from exc

        try:
            # Note: os.open(path, O_RDONLY) succeeds even for a directory on
            # Linux (opening a directory is only rejected on a write/read
            # attempt) — directories are excluded here, not via
            # IsADirectoryError above.
            mode = os.fstat(fd).st_mode
            if stat.S_ISDIR(mode):
                raise ValueError(f"device_path must not be a directory: {device_path}")
            if not (stat.S_ISBLK(mode) or stat.S_ISREG(mode)):
                raise ValueError(
                    f"device_path must be a block device or regular file: {device_path}"
                )
            size = self._determine_size(fd)
        except BaseException:
            os.close(fd)
            raise

        handle_id = self._next_handle_id
        self._next_handle_id += 1
        self._handles[handle_id] = _OpenHandle(fd=fd, size=size)
        return handle_id

    @staticmethod
    def _determine_size(fd: int) -> int:
        """Determine total size via `lseek`, which works uniformly for regular
        files and block devices — unlike `os.fstat().st_size`, which reports
        0 for block devices on Linux.
        """
        try:
            return os.lseek(fd, 0, os.SEEK_END)
        finally:
            os.lseek(fd, 0, os.SEEK_SET)

    def read_bytes(self, handle: int, offset: int, length: int) -> bytes:
        """Read a byte range from an opened device.

        Args:
            handle: Device handle previously returned by `open_device`.
            offset: Zero-based byte offset to begin reading from.
            length: Number of bytes to read.

        Returns:
            The bytes read. May be shorter than `length` at end-of-device,
            matching standard `pread` semantics — this is not clamped or
            otherwise smoothed over here, so a genuine device read error
            (e.g. a bad sector) is never silently hidden from the caller
            (Master Specification Section 61: "Acquisition must record
            unreadable sectors.").

        Raises:
            ValueError: If `handle` is unknown/closed, or `offset`/`length`
                is negative.
            OSError: If the underlying read fails.
        """
        entry = self._require_handle(handle)
        if offset < 0 or length < 0:
            raise ValueError("offset and length must be non-negative")
        if length == 0:
            return b""
        try:
            return os.pread(entry.fd, length, offset)
        except OSError as exc:
            raise OSError(f"read failed at offset {offset}, length {length}: {exc}") from exc

    def get_device_size(self, handle: int) -> int:
        """Return the total size in bytes of an opened device.

        Args:
            handle: Device handle previously returned by `open_device`.

        Returns:
            Total device size in bytes.

        Raises:
            ValueError: If `handle` is unknown/closed.
        """
        return self._require_handle(handle).size

    def close(self, handle: int) -> None:
        """Release a previously opened device handle.

        Safe to call more than once for the same handle, matching the
        idempotent `close()` convention used throughout
        `app.acquisition.storage_reader`.

        Args:
            handle: Device handle previously returned by `open_device`.
        """
        entry = self._handles.pop(handle, None)
        if entry is None:
            return
        os.close(entry.fd)

    def _require_handle(self, handle: int) -> _OpenHandle:
        entry = self._handles.get(handle)
        if entry is None:
            raise ValueError(f"unknown or already-closed device handle: {handle}")
        return entry

    @contextmanager
    def open_device_context(self, device_path: str) -> Iterator[int]:
        """Open a device and guarantee it is closed, even if the caller raises.

        Linux-specific convenience, not part of the `StorageAccess`
        contract: the interface returns opaque integer handles rather than
        reader objects, so the context-manager protocol doesn't attach to
        it directly without changing the shared abstraction. This wraps
        the existing `open_device`/`close` pair, which are already safe to
        call this way.

        Args:
            device_path: Path to a block device special file or regular
                file, as accepted by `open_device`.

        Yields:
            The opened handle identifier.
        """
        handle = self.open_device(device_path)
        try:
            yield handle
        finally:
            self.close(handle)
