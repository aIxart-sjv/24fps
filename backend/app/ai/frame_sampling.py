"""
Deterministic frame-selection strategies (task Phase 13 scope: "Do not
blindly process every frame of every recording by default... Support a
controlled frame-selection strategy... Record the sampling parameters in
AI job metadata.").

Pure computation over `(frame_count, source_fps)` -- no video I/O. Every
analysis type in one AI job (object/face detection, motion detection,
tracking) is run over the identical selected-frame sequence this module
produces, so there is exactly one sampling regime per job, not several.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["FrameSelection", "SamplingStrategy", "select_frames"]


class SamplingStrategy(str, Enum):
    """The supported frame-selection strategies (task Phase 13 scope's own
    examples: "configured FPS sampling... keyframe-oriented sampling...
    interval sampling... full-frame processing where explicitly
    requested")."""

    #: Sample at a configured target frames-per-second, rounded to the
    #: nearest whole-frame step of the source video's own fps.
    FPS = "fps"
    #: Sample every Nth source frame.
    INTERVAL = "interval"
    #: Process every frame -- only when explicitly requested (task: "Do
    #: not silently make an investigator believe every frame was analyzed
    #: when it was not").
    ALL = "all"


@dataclass(frozen=True)
class FrameSelection:
    """One selected frame: its index in the source video and its
    timestamp relative to the start of that video."""

    frame_number: int
    timestamp_seconds: float


def select_frames(
    *,
    frame_count: int,
    source_fps: float,
    strategy: SamplingStrategy,
    value: float | None = None,
) -> list[FrameSelection]:
    """Select which frame numbers to process, per the given strategy.

    Args:
        frame_count: Total decodable frames in the source video, as
            reported by the decoder. `<= 0` yields an empty selection
            (task: "Handle... empty recording" -- never invented frames).
        source_fps: The source video's own frame rate. `<= 0` yields an
            empty selection.
        strategy: Which sampling strategy to apply.
        value: Strategy-specific parameter -- target frames-per-second for
            `FPS` (default `1.0` if omitted), or the frame interval for
            `INTERVAL` (must be `>= 1`). Ignored for `ALL`.

    Returns:
        Selected frames in ascending order, always including frame `0`
        when `frame_count > 0`.

    Raises:
        ValueError: If `strategy` requires `value` and it is missing or
            out of range.
    """
    if frame_count <= 0 or source_fps <= 0:
        return []

    if strategy is SamplingStrategy.ALL:
        step = 1
    elif strategy is SamplingStrategy.INTERVAL:
        if value is None or value < 1:
            raise ValueError("interval sampling requires a value >= 1 (frames)")
        step = max(1, round(value))
    elif strategy is SamplingStrategy.FPS:
        target_fps = value if value is not None else 1.0
        if target_fps <= 0:
            raise ValueError("fps sampling requires a value > 0")
        step = max(1, round(source_fps / target_fps))
    else:  # pragma: no cover - exhaustive over SamplingStrategy
        raise ValueError(f"unsupported sampling strategy: {strategy!r}")

    return [
        FrameSelection(frame_number=n, timestamp_seconds=n / source_fps)
        for n in range(0, frame_count, step)
    ]
