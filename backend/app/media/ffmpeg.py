"""
FFmpeg subprocess wrapper.
Master Specification Section 19 ("Video Extraction"): "FFmpeg must NOT be
treated as the proprietary filesystem parser." This module knows nothing
about any vendor's container/record format — it only knows how to invoke
the `ffmpeg` binary safely and report what happened. Vendor-specific
reassembly of a proprietary format into a standard elementary stream (e.g.
`app.adapters.cp_plus.extraction`) happens entirely before this module is
ever called.

`ffmpeg` is treated as an optional runtime dependency, the same way
`pyewf` is in `app.acquisition.e01_handler`: if the configured binary is
not available, callers get a clean "unavailable" signal rather than a
crash, so the rest of the backend (and its test suite) keeps working in an
environment without FFmpeg installed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.utils.subprocess import SubprocessResult, run_subprocess


@dataclass(frozen=True)
class FFmpegResult:
    """Outcome of one FFmpeg invocation."""

    args: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool

    @property
    def ok(self) -> bool:
        """Whether FFmpeg exited with status 0 and did not time out."""
        return not self.timed_out and self.returncode == 0

    @classmethod
    def _from_subprocess_result(cls, result: SubprocessResult) -> FFmpegResult:
        return cls(
            args=result.args,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=result.duration_seconds,
            timed_out=result.timed_out,
        )


def is_ffmpeg_available() -> bool:
    """Return whether the configured FFmpeg executable can actually be run.

    Returns:
        True if `settings.ffmpeg_path` resolves to a runnable executable.
    """
    return get_ffmpeg_version() is not None


def get_ffmpeg_version() -> str | None:
    """Return the configured FFmpeg build's version string, if it is runnable.

    Returns:
        The first line of `ffmpeg -version` output (e.g.
        `"ffmpeg version n8.1.2 Copyright (c) 2000-2026 the FFmpeg
        developers"`), or `None` if the executable is missing or could not
        be run.
    """
    settings = get_settings()
    try:
        result = run_subprocess([settings.ffmpeg_path, "-version"], timeout=10)
    except FileNotFoundError:
        return None
    if not result.ok:
        return None
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    return first_line or None


def run_ffmpeg(args: list[str], *, timeout: float | None = None) -> FFmpegResult:
    """Run the configured FFmpeg executable with an explicit argument list.

    Args:
        args: FFmpeg arguments, excluding the executable itself (e.g.
            `["-y", "-f", "hevc", "-i", str(in_path), "-c", "copy",
            str(out_path)]`). Every path must already be a separate list
            element — never build a shell command string from a filename
            (Phase 9 task scope: "Use argument arrays and explicit
            executable paths").
        timeout: Maximum seconds to allow FFmpeg to run.

    Returns:
        An `FFmpegResult` describing the invocation's outcome. Never
        raises for a non-zero FFmpeg exit code — callers inspect `ok`/
        `returncode`/`stderr`.

    Raises:
        FileNotFoundError: If the configured FFmpeg executable does not
            exist. Unlike a normal FFmpeg failure (bad input, unsupported
            codec, ...), a missing binary is a configuration problem the
            caller should be told about explicitly rather than silently
            treated as "extraction failed".
    """
    settings = get_settings()
    result = run_subprocess([settings.ffmpeg_path, *args], timeout=timeout)
    return FFmpegResult._from_subprocess_result(result)
