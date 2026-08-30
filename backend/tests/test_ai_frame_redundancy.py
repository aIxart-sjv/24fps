"""Tests for app/ai/frame_redundancy.py (Phase 21, Part B) -- deterministic
frame-redundancy evaluation over synthetic numpy frames, no real video
needed."""

from __future__ import annotations

import numpy as np

from app.ai.frame_redundancy import (
    AnalyzeReason,
    FrameRedundancyConfig,
    SkipReason,
    evaluate_redundancy_sequence,
    summarize,
)


def _blank_frame(size: int = 50, value: int = 0) -> np.ndarray:
    return np.full((size, size, 3), value, dtype=np.uint8)


def _frame_with_square(*, size: int = 50, x: int, square_size: int = 10) -> np.ndarray:
    frame = _blank_frame(size)
    frame[5 : 5 + square_size, x : x + square_size] = 255
    return frame


class TestBasicRedundancyDecisions:
    def test_identical_frames_are_skipped_after_the_first(self) -> None:
        frame = _blank_frame()
        samples = [(i, i / 5.0, frame.copy()) for i in range(5)]
        config = FrameRedundancyConfig(threshold=1.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[0].analyze is True
        assert decisions[0].reason == AnalyzeReason.FIRST_FRAME
        for decision in decisions[1:]:
            assert decision.analyze is False
            assert decision.reason == SkipReason.NO_MEANINGFUL_CHANGE
            assert decision.difference_score == 0.0

    def test_tiny_difference_below_threshold_is_skipped(self) -> None:
        base = _blank_frame(value=100)
        slightly_different = _blank_frame(value=101)
        samples = [(0, 0.0, base), (1, 0.1, slightly_different)]
        config = FrameRedundancyConfig(threshold=5.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].analyze is False
        assert decisions[1].reason == SkipReason.BELOW_DIFFERENCE_THRESHOLD
        assert decisions[1].difference_score == 1.0

    def test_change_above_threshold_is_analyzed(self) -> None:
        samples = [
            (0, 0.0, _blank_frame()),
            (1, 0.1, _frame_with_square(x=10)),
        ]
        config = FrameRedundancyConfig(threshold=1.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].analyze is True
        assert decisions[1].reason == AnalyzeReason.ABOVE_DIFFERENCE_THRESHOLD
        assert decisions[1].difference_score is not None
        assert decisions[1].difference_score > 1.0

    def test_threshold_boundary_is_inclusive_of_skip(self) -> None:
        base = _blank_frame(value=100)
        exactly_at_threshold = _blank_frame(value=104)  # mean abs diff == 4.0
        samples = [(0, 0.0, base), (1, 0.1, exactly_at_threshold)]
        config = FrameRedundancyConfig(threshold=4.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].difference_score == 4.0
        assert decisions[1].analyze is False
        assert decisions[1].reason == SkipReason.BELOW_DIFFERENCE_THRESHOLD

    def test_just_above_threshold_boundary_analyzes(self) -> None:
        base = _blank_frame(value=100)
        just_over = _blank_frame(value=105)  # mean abs diff == 5.0
        samples = [(0, 0.0, base), (1, 0.1, just_over)]
        config = FrameRedundancyConfig(threshold=4.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].analyze is True
        assert decisions[1].reason == AnalyzeReason.ABOVE_DIFFERENCE_THRESHOLD

    def test_first_frame_is_always_analyzed(self) -> None:
        samples = [(0, 0.0, _blank_frame())]
        config = FrameRedundancyConfig(threshold=0.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[0].analyze is True
        assert decisions[0].reason == AnalyzeReason.FIRST_FRAME
        assert decisions[0].difference_score is None


class TestFailSafeBehavior:
    def test_different_dimensions_forces_analysis(self) -> None:
        samples = [
            (0, 0.0, _blank_frame(size=50)),
            (1, 0.1, _blank_frame(size=80)),
        ]
        config = FrameRedundancyConfig(threshold=100.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].analyze is True
        assert decisions[1].reason == AnalyzeReason.DIMENSION_MISMATCH

    def test_malformed_frame_forces_analysis(self) -> None:
        samples: list[tuple[int, float, object]] = [
            (0, 0.0, _blank_frame()),
            (1, 0.1, None),
        ]
        config = FrameRedundancyConfig(threshold=100.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].analyze is True
        assert decisions[1].reason == AnalyzeReason.COMPARISON_ERROR

    def test_comparison_error_from_unexpected_object_forces_analysis(self) -> None:
        # A non-ndarray, non-None object should hit the same fail-safe
        # path (never crash the whole evaluation).
        samples: list[tuple[int, float, object]] = [
            (0, 0.0, _blank_frame()),
            (1, 0.1, "not-a-frame"),
        ]
        config = FrameRedundancyConfig(threshold=100.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].analyze is True
        assert decisions[1].reason == AnalyzeReason.COMPARISON_ERROR

    def test_timestamp_discontinuity_forces_analysis(self) -> None:
        frame = _blank_frame()
        samples = [(0, 0.0, frame.copy()), (1, 50.0, frame.copy())]
        config = FrameRedundancyConfig(threshold=100.0, max_timestamp_gap_seconds=5.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].analyze is True
        assert decisions[1].reason == AnalyzeReason.TIMESTAMP_DISCONTINUITY

    def test_timestamp_gap_within_limit_does_not_force_analysis(self) -> None:
        frame = _blank_frame()
        samples = [(0, 0.0, frame.copy()), (1, 1.0, frame.copy())]
        config = FrameRedundancyConfig(threshold=100.0, max_timestamp_gap_seconds=5.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].analyze is False

    def test_force_analyze_frame_numbers_overrides_redundancy(self) -> None:
        frame = _blank_frame()
        samples = [(0, 0.0, frame.copy()), (5, 1.0, frame.copy())]
        config = FrameRedundancyConfig(threshold=100.0, force_analyze_frame_numbers=frozenset({5}))

        decisions = evaluate_redundancy_sequence(samples, config)

        assert decisions[1].analyze is True
        assert decisions[1].reason == AnalyzeReason.TRACKING_SAFETY_OVERRIDE


class TestPeriodicForcedAnalysis:
    def test_max_skip_run_forces_analysis_after_configured_run_length(self) -> None:
        frame = _blank_frame()
        samples = [(i, i / 10.0, frame.copy()) for i in range(6)]
        config = FrameRedundancyConfig(threshold=100.0, max_skip_run=3)

        decisions = evaluate_redundancy_sequence(samples, config)

        # frame 0: FIRST_FRAME (analyze). frames 1,2: skip (run=1,2).
        # frame 3: run would become 3 >= max_skip_run=3 -> forced analyze.
        assert decisions[0].analyze is True
        assert decisions[1].analyze is False
        assert decisions[2].analyze is False
        assert decisions[3].analyze is True
        assert decisions[3].reason == AnalyzeReason.PERIODIC_FORCED_ANALYSIS

    def test_no_max_skip_run_never_forces_periodic_analysis(self) -> None:
        frame = _blank_frame()
        samples = [(i, i / 10.0, frame.copy()) for i in range(20)]
        config = FrameRedundancyConfig(threshold=100.0, max_skip_run=None)

        decisions = evaluate_redundancy_sequence(samples, config)

        reasons = {d.reason for d in decisions}
        assert AnalyzeReason.PERIODIC_FORCED_ANALYSIS not in reasons


class TestTemporalPreservation:
    def test_frame_numbers_and_timestamps_are_preserved_unchanged(self) -> None:
        frame = _blank_frame()
        samples = [(100, 10.0, frame.copy()), (250, 25.5, frame.copy()), (400, 40.0, frame.copy())]
        config = FrameRedundancyConfig(threshold=1.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert [d.frame_number for d in decisions] == [100, 250, 400]
        assert [d.timestamp_seconds for d in decisions] == [10.0, 25.5, 40.0]

    def test_output_length_matches_input_length(self) -> None:
        frame = _blank_frame()
        samples = [(i, i * 0.5, frame.copy()) for i in range(37)]
        config = FrameRedundancyConfig(threshold=1.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        assert len(decisions) == len(samples)


class TestSummarize:
    def test_stats_counts_and_ratio_are_correct(self) -> None:
        frame = _blank_frame()
        changed = _frame_with_square(x=10)
        samples = [
            (0, 0.0, frame.copy()),
            (1, 0.1, frame.copy()),
            (2, 0.2, frame.copy()),
            (3, 0.3, changed),
        ]
        config = FrameRedundancyConfig(threshold=1.0)
        decisions = evaluate_redundancy_sequence(samples, config)

        stats = summarize(decisions, threshold=config.threshold, comparison_time_seconds=0.01)

        assert stats.total_frames == 4
        assert stats.analyzed_count == 2  # first frame + the changed frame
        assert stats.skipped_count == 2
        assert stats.skip_ratio == 0.5
        assert stats.redundant_frame_count == 2
        assert stats.comparison_method == "grayscale_mean_absolute_difference"
        assert stats.reference_strategy == "last_analyzed_frame"
        assert stats.threshold == 1.0
        assert stats.comparison_time_seconds == 0.01
        assert stats.skip_reason_counts.get("no_meaningful_change") == 2
        assert stats.analyze_reason_counts.get("first_frame") == 1
        assert stats.analyze_reason_counts.get("above_difference_threshold") == 1

    def test_empty_sequence_has_zero_ratio(self) -> None:
        stats = summarize([], threshold=1.0, comparison_time_seconds=0.0)
        assert stats.total_frames == 0
        assert stats.skip_ratio == 0.0


class TestCascadedDriftPrevention:
    def test_gradual_drift_below_per_step_threshold_still_eventually_triggers_analysis(
        self,
    ) -> None:
        """Reference-vs-last-analyzed-frame strategy: each individual
        step's difference from the *previous* decoded frame might be
        small, but cumulative drift from the last analyzed frame must
        still cross threshold and trigger a real analysis -- this is the
        exact scenario the "last analyzed frame" reference strategy
        exists to catch (see module docstring)."""
        # Each frame is 1 gray level brighter than the last (per-step
        # diff = 1.0), but by frame 5 the cumulative diff from frame 0
        # is 5.0, which exceeds threshold=3.0.
        samples = [(i, i * 0.1, _blank_frame(value=100 + i)) for i in range(8)]
        config = FrameRedundancyConfig(threshold=3.0)

        decisions = evaluate_redundancy_sequence(samples, config)

        # Frame 0 always analyzed (FIRST_FRAME). Frames 1-3 stay within
        # 3.0 of frame 0's brightness (100) -> skip. Frame 4 (value=104,
        # diff=4.0 from reference 100) exceeds threshold -> analyze, and
        # becomes the new reference.
        assert decisions[0].analyze is True
        assert decisions[1].analyze is False
        assert decisions[2].analyze is False
        assert decisions[3].analyze is False
        assert decisions[4].analyze is True
        assert decisions[4].reason == AnalyzeReason.ABOVE_DIFFERENCE_THRESHOLD
