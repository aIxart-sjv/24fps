"""
Deterministic frame-redundancy evaluation for AI analysis (Phase 21,
Part B, "Deterministic Video Frame-Redundancy Optimization").

Pure, DB-free, model-free: given a sequence of already-decoded, already-
sampled frames (the exact same `(frame_number, timestamp_seconds, frame)`
tuples `app.core.ai_manager.AIManager` builds from `app.ai.frame_sampling.
select_frames`), decides which frames are visually indistinguishable
enough from the last frame that was actually analyzed that expensive
model inference (object/face detection) may be skipped for them. This is
a pure COMPUTATION-scheduling optimization -- it never touches source
video, source timestamps, frame numbering, or frame ordering; every
frame that was sampled is still represented in the output, one
`FrameDecision` each, whether analyzed or skipped.

============================================================================
COMPARISON METHOD
============================================================================
Grayscale mean absolute difference: convert both frames to 8-bit
grayscale (`cv2.cvtColor(..., cv2.COLOR_BGR2GRAY)`), take the per-pixel
absolute difference (`cv2.absdiff`), and average it to one scalar in
[0, 255] (`.mean()`). Deterministic classical computer vision, per
`docs/SIH_TECH_STACK.md` Section 11's "use the simplest method that
works" -- no learned similarity model. This reuses the same OpenCV
primitive family `app.ai.motion_detection` already uses (`cv2.absdiff`
on grayscale), applied independently: motion detection extracts
*spatial* changed regions via contour detection; this module reduces a
whole-frame comparison to one *global* scalar. The two compute genuinely
different things, so no shared helper is factored out between them.

============================================================================
THRESHOLD
============================================================================
`difference <= threshold` -> candidate redundant (below-threshold
change); `difference > threshold` -> analyze. `threshold` is a required,
explicit parameter (`FrameRedundancyConfig.threshold`) on the same 0-255
scale as the raw mean absolute difference -- never a hardcoded magic
number; the caller (`app.core.ai_manager.AIManager`) records the exact
value used in `Job.parameters` for every run.

============================================================================
REFERENCE-FRAME STRATEGY
============================================================================
Every frame is compared against the LAST-ANALYZED frame (not the
immediately-preceding decoded frame in sampling order). This is
deliberate: comparing only to the immediately-preceding frame allows
"cascaded skipping" -- a slow, gradual scene drift where each individual
consecutive-frame delta stays under threshold, but the cumulative change
since the last real analysis becomes significant. Because the reference
here only updates when a frame is actually analyzed, each skip decision
is made against a fixed point, and cumulative drift eventually exceeds
`threshold` and triggers a real analysis (self-correcting).

============================================================================
FAIL-SAFE PHILOSOPHY (non-negotiable)
============================================================================
Whenever this module cannot confidently establish that a frame is
redundant, it returns an "analyze" decision: no reference frame yet
(`REFERENCE_MISSING`), the very first frame (`FIRST_FRAME`), a decode/
comparison error (`COMPARISON_ERROR`), mismatched frame dimensions
(`DIMENSION_MISMATCH`), an unexpectedly large gap between this frame's
timestamp and the reference's (`TIMESTAMP_DISCONTINUITY`), or an
explicit caller-supplied override (`TRACKING_SAFETY_OVERRIDE`, for a
future caller that needs specific frames force-analyzed for tracking
continuity even though this module itself never touches
`app.ai.tracking`). False negatives (analyzing a frame that turns out to
have been redundant) are acceptable; false-positive skips of a
meaningful change are not.

============================================================================
"REDUNDANT_FRAME" AS AN AGGREGATE CATEGORY
============================================================================
Two distinct, more precise skip reasons exist at the per-frame level --
`NO_MEANINGFUL_CHANGE` (difference is exactly zero) and
`BELOW_DIFFERENCE_THRESHOLD` (difference is nonzero but at/under
`threshold`). `REDUNDANT_FRAME` is not a third per-frame reason; it is
the aggregate label `summarize()` reports for "either of the above" --
i.e. the total count of frames this module decided were safe to skip,
regardless of which specific sub-reason applied. Reporting code and
tests should read `FrameRedundancyStats.redundant_frame_count` for the
aggregate and `skip_reason_counts` for the per-reason breakdown.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import cv2
import numpy as np

__all__ = [
    "COMPARISON_METHOD",
    "REFERENCE_STRATEGY",
    "AnalyzeReason",
    "FrameDecision",
    "FrameRedundancyConfig",
    "FrameRedundancyStats",
    "SkipReason",
    "aggregate_stats",
    "evaluate_redundancy_sequence",
    "summarize",
]

#: Recorded verbatim in `Job.parameters`/`FrameRedundancyStats` so a
#: reader of persisted results never has to guess which algorithm ran.
COMPARISON_METHOD = "grayscale_mean_absolute_difference"
REFERENCE_STRATEGY = "last_analyzed_frame"


class SkipReason(str, Enum):
    """Why a frame's model inference was safely skipped. See the module
    docstring's "REDUNDANT_FRAME as an aggregate category" section for
    how these two relate to the third documented vocabulary term."""

    #: The computed difference score is exactly `0.0`.
    NO_MEANINGFUL_CHANGE = "no_meaningful_change"
    #: The computed difference score is nonzero but `<= threshold`.
    BELOW_DIFFERENCE_THRESHOLD = "below_difference_threshold"


class AnalyzeReason(str, Enum):
    """Why a frame was force-analyzed -- either a genuine, real change,
    or a fail-safe override triggered by uncertainty."""

    #: The computed difference score exceeds `threshold`: an ordinary,
    #: expected reason to analyze -- not a fail-safe override.
    ABOVE_DIFFERENCE_THRESHOLD = "above_difference_threshold"
    #: The very first frame in the sequence has no reference yet.
    FIRST_FRAME = "first_frame"
    #: No reference frame is available (defensive; in practice only
    #: reachable together with `FIRST_FRAME` in this implementation).
    REFERENCE_MISSING = "reference_missing"
    #: Comparing this frame against the reference raised an unexpected
    #: error (e.g. an unreadable/corrupt decoded frame array).
    COMPARISON_ERROR = "comparison_error"
    #: This frame's dimensions do not match the reference frame's.
    DIMENSION_MISMATCH = "dimension_mismatch"
    #: The gap between this frame's timestamp and the reference frame's
    #: timestamp exceeds `FrameRedundancyConfig.max_timestamp_gap_seconds`
    #: -- treated as a possible seek/discontinuity in the source, not an
    #: ordinary consecutive frame.
    TIMESTAMP_DISCONTINUITY = "timestamp_discontinuity"
    #: A caller explicitly marked this frame number as must-analyze
    #: (`FrameRedundancyConfig.force_analyze_frame_numbers`) -- reserved
    #: for a future caller that combines this evaluator with tracking-
    #: adjacent scheduling; this AIManager integration never touches
    #: `app.ai.tracking` (tracking always analyzes every one of its own
    #: sampled frames, unconditionally -- see `app.core.ai_manager`).
    TRACKING_SAFETY_OVERRIDE = "tracking_safety_override"
    #: `FrameRedundancyConfig.max_skip_run` was reached -- a bounded
    #: safety net against an unbounded run of skipped frames (e.g. a
    #: static camera pointed at an empty room for a long stretch),
    #: independent of the difference score.
    PERIODIC_FORCED_ANALYSIS = "periodic_forced_analysis"


@dataclass(frozen=True)
class FrameRedundancyConfig:
    """Configuration for one redundancy-evaluation run. Every field is
    recorded verbatim by the caller into `Job.parameters` -- never a
    silently-applied default the caller cannot see.

    Attributes:
        threshold: Grayscale mean absolute difference (0-255 scale)
            at/under which a frame is a redundancy candidate.
        max_skip_run: If set, force-analyze after this many consecutive
            skips, regardless of difference score. `None` disables this
            safety net (redundancy is then bounded only by the
            difference threshold itself).
        max_timestamp_gap_seconds: If set, force-analyze when the gap
            between a frame's timestamp and the reference frame's
            timestamp exceeds this many seconds. `None` disables this
            check. `app.core.ai_manager.AIManager` derives this from the
            job's actual sampling interval rather than hardcoding one
            value for every job (see that module for the derivation).
        force_analyze_frame_numbers: Frame numbers that must always be
            analyzed regardless of the computed difference (see
            `AnalyzeReason.TRACKING_SAFETY_OVERRIDE`).
    """

    threshold: float
    max_skip_run: int | None = None
    max_timestamp_gap_seconds: float | None = None
    force_analyze_frame_numbers: frozenset[int] = field(default_factory=frozenset)


@dataclass(frozen=True)
class FrameDecision:
    """One frame's redundancy-evaluation outcome. Preserves the frame's
    real `frame_number`/`timestamp_seconds` unchanged -- this module
    never renumbers or reorders frames."""

    frame_number: int
    timestamp_seconds: float
    analyze: bool
    reason: SkipReason | AnalyzeReason
    difference_score: float | None


@dataclass(frozen=True)
class FrameRedundancyStats:
    """Aggregate statistics for one redundancy-evaluation run -- what
    `app.core.ai_manager.AIManager` records into `Job.parameters` (task
    Phase 21 Part B: "prefer existing Job.parameters... no per-frame
    skip records unless genuinely required")."""

    total_frames: int
    analyzed_count: int
    skipped_count: int
    skip_ratio: float
    comparison_method: str
    threshold: float
    reference_strategy: str
    redundant_frame_count: int
    skip_reason_counts: dict[str, int]
    analyze_reason_counts: dict[str, int]
    comparison_time_seconds: float

    def as_dict(self) -> dict[str, object]:
        """JSON-serializable form for `Job.parameters`."""
        return {
            "total_frames": self.total_frames,
            "analyzed_count": self.analyzed_count,
            "skipped_count": self.skipped_count,
            "skip_ratio": self.skip_ratio,
            "comparison_method": self.comparison_method,
            "threshold": self.threshold,
            "reference_strategy": self.reference_strategy,
            "redundant_frame_count": self.redundant_frame_count,
            "skip_reason_counts": self.skip_reason_counts,
            "analyze_reason_counts": self.analyze_reason_counts,
            "comparison_time_seconds": self.comparison_time_seconds,
        }


def _grayscale_mean_abs_diff(reference: Any, candidate: Any) -> float:
    """Raises on any unexpected condition -- callers treat any exception
    as `AnalyzeReason.COMPARISON_ERROR` (fail-safe: analyze)."""
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    candidate_gray = cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY)
    return float(cv2.absdiff(reference_gray, candidate_gray).mean())


def evaluate_redundancy_sequence(
    samples: Sequence[tuple[int, float, Any]],
    config: FrameRedundancyConfig,
) -> list[FrameDecision]:
    """Evaluate redundancy for a full sequence of sampled frames, in order.

    Args:
        samples: `(frame_number, timestamp_seconds, frame)` tuples, in
            ascending time order -- the exact same sequence
            `app.core.ai_manager.AIManager` decodes via
            `app.ai.frame_sampling.select_frames`. `frame` is a decoded
            BGR `numpy.ndarray`.
        config: See `FrameRedundancyConfig`.

    Returns:
        One `FrameDecision` per input sample, in the same order, with
        `frame_number`/`timestamp_seconds` preserved unchanged.
    """
    decisions: list[FrameDecision] = []
    reference_frame: Any | None = None
    reference_timestamp: float | None = None
    skip_run_length = 0

    for index, (frame_number, timestamp_seconds, frame) in enumerate(samples):
        decision = _evaluate_one_frame(
            index=index,
            frame_number=frame_number,
            timestamp_seconds=timestamp_seconds,
            frame=frame,
            reference_frame=reference_frame,
            reference_timestamp=reference_timestamp,
            config=config,
            skip_run_length=skip_run_length,
        )
        decisions.append(decision)

        if decision.analyze:
            reference_frame = frame
            reference_timestamp = timestamp_seconds
            skip_run_length = 0
        else:
            skip_run_length += 1

    return decisions


def _evaluate_one_frame(
    *,
    index: int,
    frame_number: int,
    timestamp_seconds: float,
    frame: Any,
    reference_frame: Any | None,
    reference_timestamp: float | None,
    config: FrameRedundancyConfig,
    skip_run_length: int,
) -> FrameDecision:
    if frame_number in config.force_analyze_frame_numbers:
        return FrameDecision(
            frame_number, timestamp_seconds, True, AnalyzeReason.TRACKING_SAFETY_OVERRIDE, None
        )

    if index == 0:
        return FrameDecision(frame_number, timestamp_seconds, True, AnalyzeReason.FIRST_FRAME, None)
    if reference_frame is None:
        return FrameDecision(
            frame_number, timestamp_seconds, True, AnalyzeReason.REFERENCE_MISSING, None
        )

    if (
        config.max_timestamp_gap_seconds is not None
        and reference_timestamp is not None
        and (
            timestamp_seconds < reference_timestamp
            or timestamp_seconds - reference_timestamp > config.max_timestamp_gap_seconds
        )
    ):
        return FrameDecision(
            frame_number, timestamp_seconds, True, AnalyzeReason.TIMESTAMP_DISCONTINUITY, None
        )

    try:
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return FrameDecision(
                frame_number, timestamp_seconds, True, AnalyzeReason.COMPARISON_ERROR, None
            )
        if frame.shape[:2] != reference_frame.shape[:2]:
            return FrameDecision(
                frame_number, timestamp_seconds, True, AnalyzeReason.DIMENSION_MISMATCH, None
            )
        difference = _grayscale_mean_abs_diff(reference_frame, frame)
    except Exception:
        # Fail-safe: any unexpected comparison failure means "uncertain",
        # and uncertain always means analyze.
        return FrameDecision(
            frame_number, timestamp_seconds, True, AnalyzeReason.COMPARISON_ERROR, None
        )

    if difference > config.threshold:
        return FrameDecision(
            frame_number,
            timestamp_seconds,
            True,
            AnalyzeReason.ABOVE_DIFFERENCE_THRESHOLD,
            difference,
        )

    if config.max_skip_run is not None and skip_run_length + 1 >= config.max_skip_run:
        return FrameDecision(
            frame_number,
            timestamp_seconds,
            True,
            AnalyzeReason.PERIODIC_FORCED_ANALYSIS,
            difference,
        )

    skip_reason = (
        SkipReason.NO_MEANINGFUL_CHANGE
        if difference == 0.0
        else SkipReason.BELOW_DIFFERENCE_THRESHOLD
    )
    return FrameDecision(frame_number, timestamp_seconds, False, skip_reason, difference)


def summarize(
    decisions: Sequence[FrameDecision],
    *,
    threshold: float,
    comparison_time_seconds: float,
) -> FrameRedundancyStats:
    """Aggregate a sequence of `FrameDecision`s into `FrameRedundancyStats`."""
    skip_reason_counts: Counter[str] = Counter()
    analyze_reason_counts: Counter[str] = Counter()
    skipped_count = 0

    for decision in decisions:
        if decision.analyze:
            assert isinstance(decision.reason, AnalyzeReason)
            analyze_reason_counts[decision.reason.value] += 1
        else:
            assert isinstance(decision.reason, SkipReason)
            skip_reason_counts[decision.reason.value] += 1
            skipped_count += 1

    total = len(decisions)
    return FrameRedundancyStats(
        total_frames=total,
        analyzed_count=total - skipped_count,
        skipped_count=skipped_count,
        skip_ratio=(skipped_count / total) if total else 0.0,
        comparison_method=COMPARISON_METHOD,
        threshold=threshold,
        reference_strategy=REFERENCE_STRATEGY,
        redundant_frame_count=skipped_count,
        skip_reason_counts=dict(skip_reason_counts),
        analyze_reason_counts=dict(analyze_reason_counts),
        comparison_time_seconds=comparison_time_seconds,
    )


def aggregate_stats(stats: Sequence[FrameRedundancyStats]) -> FrameRedundancyStats | None:
    """Combine per-recording `FrameRedundancyStats` into one job-level
    summary (`app.core.ai_manager.AIManager.run_job` processes multiple
    recordings per job). `threshold`/`comparison_method`/
    `reference_strategy` are carried over from the first entry -- every
    entry in one job run shares the same configuration, since it comes
    from the same job's parameters.

    Returns `None` for an empty input (nothing to aggregate).
    """
    if not stats:
        return None

    skip_reason_counts: Counter[str] = Counter()
    analyze_reason_counts: Counter[str] = Counter()
    total_frames = 0
    skipped_count = 0
    comparison_time_seconds = 0.0

    for entry in stats:
        total_frames += entry.total_frames
        skipped_count += entry.skipped_count
        comparison_time_seconds += entry.comparison_time_seconds
        skip_reason_counts.update(entry.skip_reason_counts)
        analyze_reason_counts.update(entry.analyze_reason_counts)

    return FrameRedundancyStats(
        total_frames=total_frames,
        analyzed_count=total_frames - skipped_count,
        skipped_count=skipped_count,
        skip_ratio=(skipped_count / total_frames) if total_frames else 0.0,
        comparison_method=stats[0].comparison_method,
        threshold=stats[0].threshold,
        reference_strategy=stats[0].reference_strategy,
        redundant_frame_count=skipped_count,
        skip_reason_counts=dict(skip_reason_counts),
        analyze_reason_counts=dict(analyze_reason_counts),
        comparison_time_seconds=comparison_time_seconds,
    )
