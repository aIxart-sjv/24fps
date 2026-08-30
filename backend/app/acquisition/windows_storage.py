"""
Location: 24fps/backend/app/acquisition/windows_storage.py

Windows implementation of the `StorageAccess` interface.

STATUS: Interface stub only. Per explicit project direction, no
Windows-specific physical/logical disk access is implemented at this
stage. This module exists so the acquisition subsystem's public
contract (`StorageAccess`) has a concrete, importable Windows target
from day one, without prematurely committing to a Windows API
integration approach before Phase 5 (Master Specification Section 89)
and before Windows deployment work formally begins (Phase 20).

When implemented, this class is expected to wrap Windows physical-drive
APIs (e.g. `\\\\.\\PhysicalDriveN` handles opened via `CreateFile` with
`FILE_FLAG_NO_BUFFERING` and read-only access, per Master Specification
Section 11) and enforce the same read-only invariant guaranteed by
`StorageAccess`.
"""

from __future__ import annotations

from app.acquisition.interface import StorageAccess, StorageDeviceDescriptor

_NOT_IMPLEMENTED_MESSAGE: str = (
    "WindowsStorageAccess is a scaffolded interface stub. "
    "Windows-specific physical disk access is implemented in "
    "Acquisition Phase 5 / Cross-Platform Packaging Phase 20 "
    "(Master Specification Section 89), not in this milestone."
)


class WindowsStorageAccess(StorageAccess):
    """Windows platform implementation of `StorageAccess`.

    Every method currently raises `NotImplementedError` with a message
    identifying the deferred implementation phase, so any accidental
    early use fails loudly rather than silently returning incorrect
    data — a hard requirement for forensic-safety code paths.
    """

    def list_devices(self) -> list[StorageDeviceDescriptor]:
        """Not yet implemented.

        Raises:
            NotImplementedError: Always, until Windows device
                enumeration is implemented.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

    def open_device(self, device_path: str) -> int:
        """Not yet implemented.

        Args:
            device_path: Windows physical drive path (e.g.
                '\\\\.\\PhysicalDrive1'). Unused in this stub.

        Raises:
            NotImplementedError: Always, until Windows device access is
                implemented.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

    def read_bytes(self, handle: int, offset: int, length: int) -> bytes:
        """Not yet implemented.

        Args:
            handle: Device handle. Unused in this stub.
            offset: Byte offset. Unused in this stub.
            length: Byte length. Unused in this stub.

        Raises:
            NotImplementedError: Always, until Windows device access is
                implemented.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

    def get_device_size(self, handle: int) -> int:
        """Not yet implemented.

        Args:
            handle: Device handle. Unused in this stub.

        Raises:
            NotImplementedError: Always, until Windows device access is
                implemented.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)

    def close(self, handle: int) -> None:
        """Not yet implemented.

        Args:
            handle: Device handle. Unused in this stub.

        Raises:
            NotImplementedError: Always, until Windows device access is
                implemented.
        """
        raise NotImplementedError(_NOT_IMPLEMENTED_MESSAGE)
