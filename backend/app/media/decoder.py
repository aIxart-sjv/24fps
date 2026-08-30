"""
FFmpeg mux/transcode operations for the recording-extraction pipeline.
Master Specification Section 19 ("Video Extraction"): vendor parser -> raw
stream/container -> FFmpeg -> decoded frames/media. This module is the
"FFmpeg" step: it never parses a proprietary DVR format itself (that
already happened upstream, e.g. in `app.adapters.cp_plus.extraction`) and
never implements a custom decoder (Phase 9 task scope: "Do not implement a
custom H.265 decoder").

Two operations, matching the Phase 9 output-format decision:
  - `mux_hevc_annexb_to_mp4`: a pure container remux (stream copy, no
    re-encoding) that preserves the vendor's original compressed H.265
    bytes exactly — the forensically authoritative "master" output.
  - `transcode_to_h264_mp4`: a real re-encode to H.264, produced purely so
    the recording is guaranteed to play back in any browser as a "preview"
    — never treated as the forensic record of truth.

Both take an already-reassembled Annex-B elementary stream as input (`-f
hevc`), never a raw vendor container.
"""

from __future__ import annotations

from pathlib import Path

from app.media.ffmpeg import FFmpegResult, run_ffmpeg

#: No audio track was found anywhere in the analyzed CP Plus evidence
#: (Phase 8 analysis report Section 9: "Audio presence: Not Determined" —
#: absence of evidence is not evidence of absence, but no audio marker was
#: found either). `-an` makes both FFmpeg operations explicit about
#: producing video-only output rather than erroring on an absent stream.
_NO_AUDIO_ARGS = ["-an"]

#: Generous but bounded — the largest single real CP Plus segment observed
#: is ~59 MB; both operations here are simple stream-copy/single-pass
#: encodes, not iterative processing, so this is a safety ceiling against a
#: hung/misbehaving FFmpeg process, not a tuned performance budget.
_DEFAULT_TIMEOUT_SECONDS = 600.0


def mux_hevc_annexb_to_mp4(
    elementary_stream_path: Path, output_path: Path, *, timeout: float = _DEFAULT_TIMEOUT_SECONDS
) -> FFmpegResult:
    """Remux a raw HEVC Annex-B elementary stream into an MP4 container.

    Uses `-c copy` — the compressed video bytes are carried through
    byte-for-byte, only the container framing changes. This is the
    forensically authoritative "master" output: never a re-encode.

    Args:
        elementary_stream_path: Path to a raw Annex-B `.h265` file (e.g.
            produced by `app.adapters.cp_plus.extraction`).
        output_path: Destination `.mp4` path. Overwritten if it already
            exists (this is always a fresh derived-artifact path prepared
            by the caller, never preserved evidence).
        timeout: Maximum seconds to allow FFmpeg to run.

    Returns:
        An `FFmpegResult`. Never raises for an FFmpeg-side failure (bad/
        empty input, unsupported stream) — callers inspect `ok`/`stderr`.

    Raises:
        FileNotFoundError: If the configured FFmpeg executable itself is
            missing (a configuration problem, not a media-processing one).
    """
    return run_ffmpeg(
        [
            "-y",
            "-f",
            "hevc",
            "-i",
            str(elementary_stream_path),
            "-c",
            "copy",
            *_NO_AUDIO_ARGS,
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        timeout=timeout,
    )


def transcode_to_h264_mp4(
    elementary_stream_path: Path,
    output_path: Path,
    *,
    crf: int = 23,
    preset: str = "veryfast",
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> FFmpegResult:
    """Transcode a raw HEVC Annex-B elementary stream to an H.264 MP4 preview.

    This re-encodes the video — the output bytes are not the vendor's
    original compressed frames. Only ever used to produce a
    browser-guaranteed-playable preview alongside the H.265 master from
    `mux_hevc_annexb_to_mp4`, never as a substitute for it.

    Args:
        elementary_stream_path: Path to a raw Annex-B `.h265` file.
        output_path: Destination `.mp4` path. Overwritten if it exists.
        crf: x264 constant-rate-factor quality setting (lower = higher
            quality/larger file). 23 is x264's own documented default.
        preset: x264 encoding-speed preset.
        timeout: Maximum seconds to allow FFmpeg to run.

    Returns:
        An `FFmpegResult`. Never raises for an FFmpeg-side failure.

    Raises:
        FileNotFoundError: If the configured FFmpeg executable itself is
            missing.
    """
    return run_ffmpeg(
        [
            "-y",
            "-f",
            "hevc",
            "-i",
            str(elementary_stream_path),
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            preset,
            *_NO_AUDIO_ARGS,
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        timeout=timeout,
    )
