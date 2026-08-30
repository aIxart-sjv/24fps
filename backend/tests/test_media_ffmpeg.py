"""Tests for the safe subprocess wrapper (app/utils/subprocess.py) and the
FFmpeg wrapper (app/media/ffmpeg.py), Phase 9.

FFmpeg is treated as an optional external tool, mirroring
`tests/test_e01_reader.py`'s `pyewf`-availability skip pattern: tests that
need a real, runnable `ffmpeg` skip cleanly (with a reason) when it is not
installed, while the missing-executable and argv-safety paths — which need
no FFmpeg at all — are exercised for real, unconditionally.
"""

from __future__ import annotations

import pytest

from app.media.ffmpeg import get_ffmpeg_version, is_ffmpeg_available, run_ffmpeg
from app.utils.subprocess import run_subprocess

requires_ffmpeg = pytest.mark.skipif(
    not is_ffmpeg_available(), reason="ffmpeg is not installed/runnable in this environment"
)


def test_run_subprocess_captures_stdout_and_exit_code():
    result = run_subprocess(["python3", "-c", "print('hello')"])
    assert result.ok
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_run_subprocess_reports_nonzero_exit_without_raising():
    result = run_subprocess(["python3", "-c", "import sys; sys.exit(3)"])
    assert result.ok is False
    assert result.returncode == 3


def test_run_subprocess_rejects_empty_argv():
    with pytest.raises(ValueError, match="argv"):
        run_subprocess([])


def test_run_subprocess_missing_executable_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        run_subprocess(["/definitely/not/a/real/executable/path"])


def test_run_subprocess_never_interprets_argv_as_shell_syntax():
    """A filename containing shell metacharacters must never be executed as a
    second command — this is the concrete injection-safety regression the
    Phase 9 task's "never build shell command strings from untrusted
    filenames" requirement guards against.
    """
    dangerous_arg = "; echo INJECTED > /tmp/should-not-exist-24fps-test; echo "
    result = run_subprocess(["python3", "-c", "import sys; print(len(sys.argv))", dangerous_arg])
    assert result.ok
    # argv[0] is the script's own name under -c; the dangerous string arrived
    # as exactly one argument, never split into separate shell commands.
    assert result.stdout.strip() == "2"


def test_get_ffmpeg_version_returns_none_when_executable_missing(monkeypatch: pytest.MonkeyPatch):
    from app.config import get_settings

    monkeypatch.setenv("FFMPEG_PATH", "/definitely/not/a/real/ffmpeg/path")
    get_settings.cache_clear()
    try:
        assert get_ffmpeg_version() is None
        assert is_ffmpeg_available() is False
    finally:
        get_settings.cache_clear()


@requires_ffmpeg
def test_get_ffmpeg_version_reports_a_version_string():
    version = get_ffmpeg_version()
    assert version is not None
    assert "ffmpeg" in version.lower()


@requires_ffmpeg
def test_run_ffmpeg_with_bad_args_reports_failure_not_raise():
    result = run_ffmpeg(["-i", "/no/such/input/file.h265", "/tmp/should-not-be-created.mp4"])
    assert result.ok is False
    assert result.returncode != 0
