"""
Real, measured per-stage resource metrics ("Processing Performance ...
from REAL runtime data" -- no manually-entered placeholder values, no
estimates).

Every value here is read directly from the operating system via the
stdlib `time` and `resource` modules (plus a best-effort `/proc/self/
status` read on Linux for current RSS). Where a platform doesn't support
a given reading (e.g. `/proc` on macOS/Windows), the corresponding field
is `None`, never a placeholder (Database Rule 11: "Unknown values must be
explicit, not fabricated.").

Since this backend has no background worker or thread pool anywhere --
every phase's own docstring documents running synchronously to completion
inside one call (see `app.core.processing_orchestrator`'s module
docstring) -- a resource-usage delta captured immediately before and
after one pipeline stage genuinely reflects that stage's own CPU/memory
activity, not a concurrent unrelated task's.
"""

from __future__ import annotations

import resource
import time
from dataclasses import dataclass
from typing import Any

__all__ = ["ResourceSnapshot", "capture_resource_snapshot", "diff_resource_snapshots"]


@dataclass(frozen=True)
class ResourceSnapshot:
    """A point-in-time reading of this process's own resource usage."""

    perf_counter: float
    cpu_user_seconds: float
    cpu_system_seconds: float
    #: `resource.getrusage(RUSAGE_SELF).ru_maxrss` -- on Linux (this
    #: backend's deployment target) this is already in KB. It is a
    #: monotonically non-decreasing high-water mark since process start,
    #: NOT stage-exclusive -- callers must present it as "process peak
    #: RSS as of this point", never as "this stage's own peak".
    peak_rss_kb: int
    #: Real point-in-time RSS from `/proc/self/status`, when readable.
    #: Unlike `peak_rss_kb`, a before/after delta of this value IS a
    #: genuine (if OS-page-granularity-coarse) measurement of memory
    #: growth actually attributable to the interval between two snapshots.
    current_rss_kb: int | None

    def as_dict(self) -> dict[str, object]:
        return {
            "perf_counter": self.perf_counter,
            "cpu_user_seconds": self.cpu_user_seconds,
            "cpu_system_seconds": self.cpu_system_seconds,
            "peak_rss_kb": self.peak_rss_kb,
            "current_rss_kb": self.current_rss_kb,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ResourceSnapshot:
        current_rss = data.get("current_rss_kb")
        return ResourceSnapshot(
            perf_counter=float(data["perf_counter"]),
            cpu_user_seconds=float(data["cpu_user_seconds"]),
            cpu_system_seconds=float(data["cpu_system_seconds"]),
            peak_rss_kb=int(data["peak_rss_kb"]),
            current_rss_kb=int(current_rss) if current_rss is not None else None,
        )


def capture_resource_snapshot() -> ResourceSnapshot:
    """Capture real, current process resource usage. Never estimated."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return ResourceSnapshot(
        perf_counter=time.perf_counter(),
        cpu_user_seconds=usage.ru_utime,
        cpu_system_seconds=usage.ru_stime,
        peak_rss_kb=usage.ru_maxrss,
        current_rss_kb=_read_current_rss_kb(),
    )


def diff_resource_snapshots(start: ResourceSnapshot, end: ResourceSnapshot) -> dict[str, object]:
    """Compute the real, measured deltas between two snapshots of the
    same process interval -- the actual payload stored on `Job.
    resource_metrics` and surfaced by the Processing Performance API.

    `runtime_seconds` uses `time.perf_counter()` (monotonic, high
    resolution, immune to wall-clock adjustments) rather than a
    `datetime` subtraction -- the high-resolution timing this task
    requires.
    """
    rss_delta_kb = (
        end.current_rss_kb - start.current_rss_kb
        if start.current_rss_kb is not None and end.current_rss_kb is not None
        else None
    )
    return {
        "start": start.as_dict(),
        "end": end.as_dict(),
        "runtime_seconds": end.perf_counter - start.perf_counter,
        "cpu_user_seconds": end.cpu_user_seconds - start.cpu_user_seconds,
        "cpu_system_seconds": end.cpu_system_seconds - start.cpu_system_seconds,
        "peak_rss_kb": end.peak_rss_kb,
        "rss_delta_kb": rss_delta_kb,
    }


def _read_current_rss_kb() -> int | None:
    """Best-effort current RSS from `/proc/self/status` (Linux only).
    Returns `None` on any platform/parsing failure -- never a guess."""
    try:
        with open("/proc/self/status", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1])
        return None
    except OSError:
        return None
