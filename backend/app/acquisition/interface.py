"""
Location: 24fps/backend/app/acquisition/interface.py

Defines the platform-independent `StorageAccess` contract used during
forensic acquisition (Master Specification Section 11, "Platform
Storage Access"). Concrete implementations (Linux, Windows) supply
OS-specific low-level device access; no other part of the forensic core
should import platform-specific device APIs directly — everything must
flow through this interface.

This module defines the CONTRACT ONLY. It contains no acquisition,
imaging, or device-enumeration logic. Concrete implementations are
completed in Acquisition Phase 5 of the development order (Master
Specification Section 89).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StorageDeviceDescriptor:
    """Describes a physical or logical storage device visible to the OS.

    Attributes:
        device_path: Platform-native path/identifier for the device
            (e.g. '/dev/sdb' on Linux, '\\\\.\\PhysicalDrive1' on Windows).
        size_bytes: Total addressable size of the device in bytes, if
            determinable without opening the device for exclusive access.
        is_read_only: Whether the OS currently reports this device as
            read-only (e.g. because a hardware write blocker is in use).
        description: Human-readable device description as reported by
            the operating system, where available.
    """

    device_path: str
    size_bytes: int | None
    is_read_only: bool
    description: str | None = None


class StorageAccess(ABC):
    """Abstract, platform-independent interface for raw storage access.

    Every concrete subclass must guarantee read-only semantics toward
    source evidence: no method on this interface may ever write to the
    underlying device. This is a hard forensic-safety invariant, not an
    implementation detail — see Master Specification Section 76, rule 1:
    "Original evidence must be treated as immutable/read-only."
    """

    @abstractmethod
    def list_devices(self) -> list[StorageDeviceDescriptor]:
        """Enumerate storage devices visible to the current platform.

        Returns:
            A list of `StorageDeviceDescriptor` objects describing each
            detected device.

        Raises:
            PermissionError: If the current process lacks the privileges
                required to enumerate storage devices.
        """
        raise NotImplementedError

    @abstractmethod
    def open_device(self, device_path: str) -> int:
        """Open a device for exclusive, read-only access.

        Args:
            device_path: Platform-native path/identifier of the device
                to open, as returned by `list_devices`.

        Returns:
            An opaque, platform-specific handle identifier that must be
            passed to subsequent `read_bytes`/`get_device_size`/`close`
            calls.

        Raises:
            FileNotFoundError: If the specified device does not exist.
            PermissionError: If the device cannot be opened read-only
                with the current process privileges.
        """
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, handle: int, offset: int, length: int) -> bytes:
        """Read a byte range from an opened device.

        Args:
            handle: Device handle previously returned by `open_device`.
            offset: Zero-based byte offset to begin reading from.
            length: Number of bytes to read.

        Returns:
            The bytes read from the device. May be shorter than
            `length` only at end-of-device.

        Raises:
            OSError: If the underlying read operation fails (e.g. due
                to a bad sector or a disconnected device).
            ValueError: If `offset` or `length` is negative.
        """
        raise NotImplementedError

    @abstractmethod
    def get_device_size(self, handle: int) -> int:
        """Return the total size in bytes of an opened device.

        Args:
            handle: Device handle previously returned by `open_device`.

        Returns:
            Total device size in bytes.

        Raises:
            OSError: If the device size cannot be determined.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self, handle: int) -> None:
        """Release a previously opened device handle.

        Args:
            handle: Device handle previously returned by `open_device`.

        Raises:
            OSError: If the handle cannot be closed cleanly.
        """
        raise NotImplementedError
