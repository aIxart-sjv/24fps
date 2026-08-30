"""Tests for LinuxStorageAccess (Master Spec Section 11, Platform Storage Access).

Exercised against regular-file fixtures rather than real block devices:
`open`/`pread`/`lseek` behave identically for a block device special file
and a regular file at the syscall level, so this is the same mechanism a
real device path would go through, not a weakened substitute for it. No
test in this file writes to or otherwise mutates a real system device.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from app.acquisition.linux_storage import LinuxStorageAccess


@pytest.fixture
def storage() -> LinuxStorageAccess:
    return LinuxStorageAccess()


@pytest.fixture
def sample_file(tmp_path: Path) -> tuple[Path, bytes]:
    content = bytes(range(256)) * 20  # 5120 bytes, deterministic and varied
    path = tmp_path / "device.img"
    path.write_bytes(content)
    return path, content


# --- open/read/size/close lifecycle ---


def test_open_device_returns_handle_and_reads_content(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, content = sample_file
    handle = storage.open_device(str(path))
    try:
        assert isinstance(handle, int)
        assert storage.read_bytes(handle, 0, len(content)) == content
    finally:
        storage.close(handle)


def test_get_device_size_matches_file_size(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, content = sample_file
    handle = storage.open_device(str(path))
    try:
        assert storage.get_device_size(handle) == len(content)
    finally:
        storage.close(handle)


def test_read_bytes_returns_exact_slice(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, content = sample_file
    handle = storage.open_device(str(path))
    try:
        assert storage.read_bytes(handle, 100, 50) == content[100:150]
    finally:
        storage.close(handle)


def test_read_bytes_does_not_move_a_shared_offset(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    """pread-based reads must be independent of read order (no stateful seek)."""
    path, content = sample_file
    handle = storage.open_device(str(path))
    try:
        first = storage.read_bytes(handle, 200, 10)
        second = storage.read_bytes(handle, 0, 10)
        third = storage.read_bytes(handle, 200, 10)
        assert first == content[200:210]
        assert second == content[0:10]
        assert third == content[200:210]
    finally:
        storage.close(handle)


# --- offsets and bounds ---


def test_read_bytes_past_end_returns_partial(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, content = sample_file
    handle = storage.open_device(str(path))
    try:
        result = storage.read_bytes(handle, len(content) - 5, 100)
        assert result == content[-5:]
    finally:
        storage.close(handle)


def test_read_bytes_at_exact_end_returns_empty(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, content = sample_file
    handle = storage.open_device(str(path))
    try:
        assert storage.read_bytes(handle, len(content), 10) == b""
    finally:
        storage.close(handle)


def test_read_bytes_zero_length_returns_empty(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, _content = sample_file
    handle = storage.open_device(str(path))
    try:
        assert storage.read_bytes(handle, 0, 0) == b""
    finally:
        storage.close(handle)


@pytest.mark.parametrize("offset,length", [(-1, 10), (0, -1), (-5, -5)])
def test_read_bytes_rejects_negative_offset_or_length(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes], offset: int, length: int
):
    path, _content = sample_file
    handle = storage.open_device(str(path))
    try:
        with pytest.raises(ValueError, match="non-negative"):
            storage.read_bytes(handle, offset, length)
    finally:
        storage.close(handle)


def test_read_bytes_unknown_handle_raises(storage: LinuxStorageAccess):
    with pytest.raises(ValueError, match="unknown or already-closed"):
        storage.read_bytes(9999, 0, 10)


def test_get_device_size_unknown_handle_raises(storage: LinuxStorageAccess):
    with pytest.raises(ValueError, match="unknown or already-closed"):
        storage.get_device_size(9999)


# --- close / context-manager behavior ---


def test_close_is_idempotent(storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]):
    path, _content = sample_file
    handle = storage.open_device(str(path))
    storage.close(handle)
    storage.close(handle)  # must not raise


def test_close_unknown_handle_is_a_noop(storage: LinuxStorageAccess):
    storage.close(9999)  # must not raise


def test_operations_after_close_raise(storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]):
    path, _content = sample_file
    handle = storage.open_device(str(path))
    storage.close(handle)
    with pytest.raises(ValueError, match="unknown or already-closed"):
        storage.read_bytes(handle, 0, 1)


def test_context_manager_closes_on_success(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, content = sample_file
    with storage.open_device_context(str(path)) as handle:
        assert storage.read_bytes(handle, 0, 10) == content[:10]
        captured_handle = handle
    with pytest.raises(ValueError, match="unknown or already-closed"):
        storage.read_bytes(captured_handle, 0, 1)


def test_context_manager_closes_on_exception(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, _content = sample_file
    captured_handle = None
    with pytest.raises(RuntimeError), storage.open_device_context(str(path)) as handle:
        captured_handle = handle
        raise RuntimeError("boom")
    assert captured_handle is not None
    with pytest.raises(ValueError, match="unknown or already-closed"):
        storage.read_bytes(captured_handle, 0, 1)


def test_multiple_handles_to_same_file_are_independent(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, content = sample_file
    handle_a = storage.open_device(str(path))
    handle_b = storage.open_device(str(path))
    try:
        assert handle_a != handle_b
        storage.close(handle_a)
        # handle_b must remain usable after handle_a is closed.
        assert storage.read_bytes(handle_b, 0, 10) == content[:10]
        with pytest.raises(ValueError, match="unknown or already-closed"):
            storage.read_bytes(handle_a, 0, 10)
    finally:
        storage.close(handle_b)


# --- device-path validation ---


@pytest.mark.parametrize("bad_path", ["", "   "])
def test_open_device_rejects_empty_path(storage: LinuxStorageAccess, bad_path: str):
    with pytest.raises(ValueError, match="non-empty"):
        storage.open_device(bad_path)


def test_open_device_rejects_null_byte(storage: LinuxStorageAccess):
    with pytest.raises(ValueError, match="null byte"):
        storage.open_device("bad\x00path")


def test_open_device_rejects_missing_path(storage: LinuxStorageAccess, tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        storage.open_device(str(tmp_path / "does_not_exist.img"))


def test_open_device_rejects_directory(storage: LinuxStorageAccess, tmp_path: Path):
    with pytest.raises(ValueError, match="must not be a directory"):
        storage.open_device(str(tmp_path))


@pytest.mark.skipif(not Path("/dev/null").exists(), reason="/dev/null is not present")
def test_open_device_rejects_a_real_character_device(storage: LinuxStorageAccess):
    """Verified against a real, always-present OS special file, not a fabricated one.

    `/dev/null` is safe to probe read-only (world-readable, no data to
    disturb); the type guard must reject it before any read is attempted.
    """
    with pytest.raises(ValueError, match="must be a block device or regular file"):
        storage.open_device("/dev/null")


@pytest.mark.skipif(os.getuid() == 0, reason="permission checks are bypassed when running as root")
def test_open_device_permission_error_is_raised_clearly(
    storage: LinuxStorageAccess, tmp_path: Path
):
    path = tmp_path / "unreadable.img"
    path.write_bytes(b"secret")
    os.chmod(path, 0o000)
    try:
        with pytest.raises(PermissionError, match="insufficient permissions"):
            storage.open_device(str(path))
    finally:
        os.chmod(path, 0o644)


# --- read-only guarantee ---


def test_open_device_requests_read_only_access_only(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    """The exact flags passed to os.open must be O_RDONLY and nothing else."""
    path, _content = sample_file
    with patch("app.acquisition.linux_storage.os.open", wraps=os.open) as mock_open:
        handle = storage.open_device(str(path))
    try:
        mock_open.assert_called_once_with(str(path), os.O_RDONLY)
    finally:
        storage.close(handle)


def test_reading_never_mutates_the_source_file(
    storage: LinuxStorageAccess, sample_file: tuple[Path, bytes]
):
    path, content = sample_file
    before_mode = stat.S_IMODE(os.stat(path).st_mode)
    before_mtime = os.stat(path).st_mtime_ns

    handle = storage.open_device(str(path))
    try:
        offset = 0
        while offset < storage.get_device_size(handle):
            chunk = storage.read_bytes(handle, offset, 37)
            if not chunk:
                break
            offset += len(chunk)
    finally:
        storage.close(handle)

    assert path.read_bytes() == content
    assert stat.S_IMODE(os.stat(path).st_mode) == before_mode
    assert os.stat(path).st_mtime_ns == before_mtime


def test_storage_access_interface_exposes_no_write_method():
    """The abstraction itself must not offer any mutating operation."""
    public_methods = {name for name in dir(LinuxStorageAccess) if not name.startswith("_")}
    assert not any("write" in name for name in public_methods)


# --- list_devices: explicitly deferred, must fail clearly, never fabricate ---


def test_list_devices_raises_not_implemented(storage: LinuxStorageAccess):
    with pytest.raises(NotImplementedError, match="not implemented"):
        storage.list_devices()


# --- large / chunked reads ---


def test_chunked_reads_reconstruct_full_content(storage: LinuxStorageAccess, tmp_path: Path):
    content = os.urandom(1_000_003)  # deliberately not a round chunk multiple
    path = tmp_path / "large.img"
    path.write_bytes(content)

    handle = storage.open_device(str(path))
    chunks: list[bytes] = []
    try:
        chunk_size = 65536
        offset = 0
        size = storage.get_device_size(handle)
        while offset < size:
            chunk = storage.read_bytes(handle, offset, chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
            offset += len(chunk)
    finally:
        storage.close(handle)

    assert b"".join(chunks) == content
