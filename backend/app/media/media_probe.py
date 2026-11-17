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
    #: The video stream's declared `r_frame_rate` (a timebase-grid guess by
    #: ffprobe, not a measurement) -- kept separate from `fps`
    #: (`avg_frame_rate`) so a caller can report a header discrepancy.
    r_frame_rate: float | None = None
    #: Only populated when `probe_media(..., count_packets=True)`: the
    #: number of video packets ffprobe actually read (== frames for the
    #: intra/inter-coded streams this project handles), and
    #: `video_packet_count / video duration` -- a *measured* average frame
    #: rate independent of whatever the container header declares.
    video_packet_count: int | None = None
    measured_fps: float | None = None
    #: `video stream start_time - container start_time`, in seconds: how far
    #: into the container's own timeline the first video frame sits. Non-zero
    #: when another stream (e.g. audio) starts first. A browser's
    #: `<video>.currentTime` runs on the container timeline, so frame N is
    #: shown at `N / fps + video_start_offset_seconds`, not `N / fps`.
    video_start_offset_seconds: float | None = None


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


def probe_media(
    path: Path, *, timeout: float | None = 30, count_packets: bool = False
) -> MediaProbeResult:
    """Inspect a media file with `ffprobe` and report what it found.

    Args:
        path: Path to the media file to probe -- normally an already-produced
            artifact (e.g. a muxed MP4), but a source evidence file that is
            already a standard container (Hikvision exports, Phase 26) may
            also be probed: `ffprobe` opens its input read-only and never
            writes to it.
        timeout: Maximum seconds to allow `ffprobe` to run.
        count_packets: Also read every video packet header (`-count_packets`;
            no decoding) so `video_packet_count`/`measured_fps` are populated.
            Costs a full pass over the file's packet headers, so it is opt-in.

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
        *(["-count_packets"] if count_packets else []),
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

    video_packet_count: int | None = None
    measured_fps: float | None = None
    if count_packets and video_stream is not None:
        try:
            video_packet_count = int(video_stream["nb_read_packets"])
        except (KeyError, TypeError, ValueError):
            video_packet_count = None
        stream_duration: float | None = None
        for candidate in (video_stream.get("duration"), format_info.get("duration")):
            try:
                stream_duration = float(candidate) if candidate is not None else None
            except (TypeError, ValueError):
                stream_duration = None
            if stream_duration:
                break
        if video_packet_count and stream_duration and stream_duration > 0:
            measured_fps = video_packet_count / stream_duration

    video_start_offset_seconds: float | None = None
    if video_stream is not None:
        try:
            video_start_offset_seconds = float(video_stream["start_time"]) - float(
                format_info["start_time"]
            )
        except (KeyError, TypeError, ValueError):
            video_start_offset_seconds = None

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
        r_frame_rate=_parse_frame_rate(video_stream.get("r_frame_rate")) if video_stream else None,
        video_packet_count=video_packet_count,
        measured_fps=measured_fps,
        video_start_offset_seconds=video_start_offset_seconds,
    )
