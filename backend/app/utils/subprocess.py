"""
Safe external-process execution.
Master Specification Section 19 ("Video Extraction"): FFmpeg is invoked as
an external tool, never as a proprietary-format parser. This module is the
one place that actually calls `subprocess` in the backend, so every caller
(FFmpeg today, potentially other CLI tools later) gets the same safety
guarantees: an argument-vector call only (never `shell=True`, never a
string command a filename could be interpolated into), explicit timeout
support, and a structured result instead of a raised
`CalledProcessError`/`TimeoutExpired` a caller would have to remember to
catch.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class SubprocessResult:
    """Outcome of one `run_subprocess` call."""

    args: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool

    @property
    def ok(self) -> bool:
        """Whether the process exited with status 0 and did not time out."""
        return not self.timed_out and self.returncode == 0


def run_subprocess(
    argv: Sequence[str], *, timeout: float | None = None, input_text: str | None = None
) -> SubprocessResult:
    """Run an external process safely and capture its outcome.

    Args:
        argv: The full argument vector, executable first (e.g.
            `["ffmpeg", "-version"]`). Never a shell string — this function
            always calls `subprocess.run` with `shell=False`, so no
            argument is ever interpreted as shell syntax regardless of
            what characters a filename or option value contains.
        timeout: Maximum seconds to allow the process to run. `None` (the
            default) waits indefinitely.
        input_text: Optional text piped to the process's stdin.

    Returns:
        A `SubprocessResult`. Never raises for a non-zero exit code or a
        timeout — both are reported via `returncode`/`timed_out` so a
        caller can decide how to treat a failed external tool without a
        try/except for control flow.

    Raises:
        ValueError: If `argv` is empty.
        FileNotFoundError: If the executable named by `argv[0]` does not
            exist — this is treated as a programmer/configuration error
            (a missing tool should fail loudly at the call site), not a
            normal external-process failure.
    """
    if not argv:
        raise ValueError("argv must contain at least the executable to run")

    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S603 - argv is always a list, never shell=True
            list(argv),
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        return SubprocessResult(
            args=tuple(argv),
            returncode=None,
            stdout=exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            duration_seconds=duration,
            timed_out=True,
        )

    duration = time.monotonic() - started
    return SubprocessResult(
        args=tuple(argv),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        duration_seconds=duration,
        timed_out=False,
    )
