"""Tests for app/ai/frame_sampling.py (Phase 13) -- pure, deterministic."""

from __future__ import annotations

import pytest

from app.ai.frame_sampling import SamplingStrategy, select_frames


def test_fps_sampling_selects_every_nth_frame() -> None:
    selections = select_frames(
        frame_count=100, source_fps=25.0, strategy=SamplingStrategy.FPS, value=1.0
    )

    assert [s.frame_number for s in selections] == [0, 25, 50, 75]
    assert selections[1].timestamp_seconds == pytest.approx(1.0)


def test_fps_sampling_default_value_is_one_fps() -> None:
    with_default = select_frames(frame_count=50, source_fps=25.0, strategy=SamplingStrategy.FPS)
    explicit = select_frames(
        frame_count=50, source_fps=25.0, strategy=SamplingStrategy.FPS, value=1.0
    )

    assert with_default == explicit


def test_interval_sampling_selects_every_nth_frame_literally() -> None:
    selections = select_frames(
        frame_count=10, source_fps=10.0, strategy=SamplingStrategy.INTERVAL, value=3
    )

    assert [s.frame_number for s in selections] == [0, 3, 6, 9]


def test_all_strategy_selects_every_frame() -> None:
    selections = select_frames(frame_count=5, source_fps=10.0, strategy=SamplingStrategy.ALL)

    assert [s.frame_number for s in selections] == [0, 1, 2, 3, 4]


def test_empty_recording_yields_no_selections() -> None:
    assert select_frames(frame_count=0, source_fps=25.0, strategy=SamplingStrategy.ALL) == []


def test_invalid_fps_yields_no_selections() -> None:
    assert select_frames(frame_count=10, source_fps=0.0, strategy=SamplingStrategy.ALL) == []


def test_interval_sampling_requires_a_value() -> None:
    with pytest.raises(ValueError, match="interval sampling requires"):
        select_frames(frame_count=10, source_fps=10.0, strategy=SamplingStrategy.INTERVAL)


def test_interval_sampling_rejects_value_below_one() -> None:
    with pytest.raises(ValueError, match="interval sampling requires"):
        select_frames(
            frame_count=10, source_fps=10.0, strategy=SamplingStrategy.INTERVAL, value=0.5
        )


def test_fps_sampling_rejects_non_positive_value() -> None:
    with pytest.raises(ValueError, match="fps sampling requires"):
        select_frames(frame_count=10, source_fps=10.0, strategy=SamplingStrategy.FPS, value=0.0)


def test_fps_sampling_faster_than_source_fps_still_selects_every_frame() -> None:
    """Requesting more fps than the source has should never skip frames or crash."""
    selections = select_frames(
        frame_count=5, source_fps=10.0, strategy=SamplingStrategy.FPS, value=100.0
    )

    assert [s.frame_number for s in selections] == [0, 1, 2, 3, 4]
