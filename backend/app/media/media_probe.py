"""
FFprobe-based media inspection.
Master Specification Section 19 ("Video Extraction"): "FFmpeg
responsibilities: media probe, container/stream identification..." — this
module is that responsibility, kept separate from `app.media.decoder`
(which performs the actual mux/transcode) so a caller can probe any media
file without needing to know how it was produced.

Never guesses a codec/resolution/duration: if `ffprobe` is unavailable or a
file cannot be parsed, every field stays `None` and `available` is `False`
(Master Specification Section 6: "If a value cannot be reliably determined,
record an explicit unavailable state. Do not guess.").
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.utils.subprocess import run_subprocess


@dataclass(frozen=True)
class MediaProbeResult:
    """What `ffprobe` could determine about one media file."""

    available: bool
    format_name: str | None = None
    duration_seconds: float | None = None
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] | None = None


def _parse_frame_rate(value: str | None) -> float | None:
    """Parse an ffprobe `"num/den"` frame-rate string into a float.

    Args:
        value: A string like `"25/1"` or `"0/0"` (the latter meaning
            "not applicable", e.g. for a still-image stream).

    Returns:
        The frame rate, or `None` if it could not be determined.
    """
    if not value or "/" not in value:
        return None
    numerator_str, _, denominator_str = value.partition("/")
    try:
        numerator = float(numerator_str)
        denominator = float(denominator_str)
    except ValueError:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def probe_media(path: Path, *, timeout: float | None = 30) -> MediaProbeResult:
    """Inspect a media file with `ffprobe` and report what it found.

    Args:
        path: Path to the media file to probe (an already-produced
            artifact, e.g. a muxed MP4 — this function never reads or
            interprets preserved source evidence).
        timeout: Maximum seconds to allow `ffprobe` to run.

    Returns:
        A `MediaProbeResult`. `available` is `False` (with the reason in
        `warnings`) whenever `ffprobe` is not installed, exits non-zero, or
        its output cannot be parsed as the expected JSON shape — never
        raises for those cases.
    """
    settings = get_settings()
    args = [
        settings.ffprobe_path,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = run_subprocess(args, timeout=timeout)
    except FileNotFoundError:
        return MediaProbeResult(
            available=False,
            warnings=[f"ffprobe executable not found at {settings.ffprobe_path!r}"],
        )

    if not result.ok:
        return MediaProbeResult(
            available=False,
            warnings=[f"ffprobe exited with status {result.returncode}: {result.stderr.strip()}"],
        )

    try:
        payload: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError:
        return MediaProbeResult(
            available=False, warnings=["ffprobe output could not be parsed as JSON"]
        )

    streams = payload.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    format_info = payload.get("format", {})

    duration_seconds: float | None = None
    raw_duration = format_info.get("duration")
    if raw_duration is not None:
        try:
            duration_seconds = float(raw_duration)
        except (TypeError, ValueError):
            duration_seconds = None

    warnings: list[str] = []
    if video_stream is None:
        warnings.append("ffprobe found no video stream in this file")

    return MediaProbeResult(
        available=True,
        format_name=format_info.get("format_name"),
        duration_seconds=duration_seconds,
        codec=video_stream.get("codec_name") if video_stream else None,
        width=video_stream.get("width") if video_stream else None,
        height=video_stream.get("height") if video_stream else None,
        fps=_parse_frame_rate(video_stream.get("avg_frame_rate")) if video_stream else None,
        warnings=warnings,
        raw=payload,
    )
