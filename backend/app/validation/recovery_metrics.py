"""
Recovery validation (Phase 14, Master Specification Section 36-37; task
Phase 14 scope section 14).

Compares an independently-known expected recovery outcome
(`GroundTruthRecoverySegment`) against Phase 10's own already-computed
`RecoveryResult`/`Recording` fields -- never recomputes recovery rate,
frame continuity, or fragment counts itself (`app.recovery.*` stays
untouched and unduplicated).

Explicitly keeps "deleted-record recovery" separate from "damaged/
truncated segment recovery": this module only reports what a given
`GroundTruthRecoverySegment`/`SystemRecoveryOutcome` pair actually says --
it never claims deleted-record-recovery accuracy from ground truth that
was never independently established for a deletion scenario.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.validation.ground_truth import GroundTruthRecoverySegment

__all__ = ["RecoveryComparison", "SystemRecoveryOutcome", "compare_recovery"]


@dataclass(frozen=True)
class SystemRecoveryOutcome:
    """The system's actual, already-computed recovery outcome (read from
    a persisted `RecoveryResult`/`Recording`, never recomputed here)."""

    status: str | None
    actual_start: datetime | None
    actual_end: datetime | None
    actual_duration_ms: int | None
    frames_recovered: int | None
    fragments_found: int | None
    fragments_used: int | None
    recovery_rate: float | None
    frame_continuity: float | None
    actual_hash: str | None


@dataclass(frozen=True)
class RecoveryComparison:
    """The full expected-vs-actual recovery comparison. Every `*_error`
    field is `None` (never fabricated) when either side lacks the value
    needed to compute it."""

    ground_truth: GroundTruthRecoverySegment
    system_outcome: SystemRecoveryOutcome
    start_error_seconds: float | None
    end_error_seconds: float | None
    duration_error_ms: int | None
    frames_error: int | None
    fragments_error: int | None
    hash_matches: bool | None


def compare_recovery(
    ground_truth: GroundTruthRecoverySegment, system_outcome: SystemRecoveryOutcome
) -> RecoveryComparison:
    """Compare an expected recovery outcome against the system's actual one.

    Args:
        ground_truth: The independently-known expected outcome.
        system_outcome: The system's actual, already-computed outcome.

    Returns:
        A `RecoveryComparison` with signed errors (`actual - expected`)
        for every field both sides have, and `None` for every field
        either side lacks.
    """
    start_error_seconds: float | None = None
    if ground_truth.expected_start is not None and system_outcome.actual_start is not None:
        start_error_seconds = (
            system_outcome.actual_start - ground_truth.expected_start
        ).total_seconds()

    end_error_seconds: float | None = None
    if ground_truth.expected_end is not None and system_outcome.actual_end is not None:
        end_error_seconds = (system_outcome.actual_end - ground_truth.expected_end).total_seconds()

    duration_error_ms: int | None = None
    if (
        ground_truth.expected_duration_ms is not None
        and system_outcome.actual_duration_ms is not None
    ):
        duration_error_ms = system_outcome.actual_duration_ms - ground_truth.expected_duration_ms

    frames_error: int | None = None
    if ground_truth.expected_frames is not None and system_outcome.frames_recovered is not None:
        frames_error = system_outcome.frames_recovered - ground_truth.expected_frames

    fragments_error: int | None = None
    if ground_truth.expected_fragments is not None and system_outcome.fragments_found is not None:
        fragments_error = system_outcome.fragments_found - ground_truth.expected_fragments

    hash_matches: bool | None = None
    if ground_truth.expected_hash is not None and system_outcome.actual_hash is not None:
        hash_matches = ground_truth.expected_hash == system_outcome.actual_hash

    return RecoveryComparison(
        ground_truth=ground_truth,
        system_outcome=system_outcome,
        start_error_seconds=start_error_seconds,
        end_error_seconds=end_error_seconds,
        duration_error_ms=duration_error_ms,
        frames_error=frames_error,
        fragments_error=fragments_error,
        hash_matches=hash_matches,
    )
