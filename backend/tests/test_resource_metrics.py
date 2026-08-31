"""Tests for app/core/resource_metrics.py (Phase 24-2: "Processing
Performance ... from REAL runtime data")."""

from __future__ import annotations

import time

from app.core.resource_metrics import (
    ResourceSnapshot,
    capture_resource_snapshot,
    diff_resource_snapshots,
)


def test_capture_resource_snapshot_returns_real_values() -> None:
    snapshot = capture_resource_snapshot()
    assert snapshot.perf_counter > 0
    assert snapshot.cpu_user_seconds >= 0
    assert snapshot.cpu_system_seconds >= 0
    # A running Python process always has a nonzero peak RSS.
    assert snapshot.peak_rss_kb > 0
    # current_rss_kb is None only when /proc/self/status is unreadable
    # (non-Linux) -- on this backend's Linux target it is always present.
    assert snapshot.current_rss_kb is None or snapshot.current_rss_kb > 0


def test_diff_resource_snapshots_measures_real_elapsed_time() -> None:
    start = capture_resource_snapshot()
    time.sleep(0.01)
    end = capture_resource_snapshot()

    diff = diff_resource_snapshots(start, end)
    assert diff["runtime_seconds"] >= 0.01
    assert diff["cpu_user_seconds"] >= 0
    assert diff["cpu_system_seconds"] >= 0
    assert diff["peak_rss_kb"] == end.peak_rss_kb


def test_diff_resource_snapshots_rss_delta_none_when_unmeasurable() -> None:
    start = ResourceSnapshot(
        perf_counter=1.0,
        cpu_user_seconds=0.0,
        cpu_system_seconds=0.0,
        peak_rss_kb=100,
        current_rss_kb=None,
    )
    end = ResourceSnapshot(
        perf_counter=2.0,
        cpu_user_seconds=0.1,
        cpu_system_seconds=0.0,
        peak_rss_kb=110,
        current_rss_kb=None,
    )
    diff = diff_resource_snapshots(start, end)
    assert diff["rss_delta_kb"] is None


def test_resource_snapshot_round_trips_through_dict() -> None:
    snapshot = capture_resource_snapshot()
    restored = ResourceSnapshot.from_dict(snapshot.as_dict())
    assert restored == snapshot
