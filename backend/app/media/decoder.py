"""
FFmpeg mux/transcode operations for the recording-extraction pipeline.
Master Specification Section 19 ("Video Extraction"): vendor parser -> raw
stream/container -> FFmpeg -> decoded frames/media. This module is the
"FFmpeg" step: it never parses a proprietary DVR format itself (that
already happened upstream, e.g. in `app.adapters.cp_plus.extraction`) and
never implements a custom decoder (Phase 9 task scope: "Do not implement a
custom H.265 decoder").

Four operations. The first two, matching the Phase 9 CP Plus output-format
decision:
  - `mux_hevc_annexb_to_mp4`: a pure container remux (stream copy, no
    re-encoding) that preserves the vendor's original compressed H.265
    bytes exactly — the forensically authoritative "master" output.
  - `transcode_to_h264_mp4`: a real re-encode to H.264, produced purely so
    the recording is guaranteed to play back in any browser as a "preview"
    — never treated as the forensic record of truth.
  Both take an already-reassembled Annex-B elementary stream as input (`-f
  hevc`), never a raw vendor container.

Phase 26 adds a third, generic pair (`remux_container_to_mp4`/
`transcode_container_to_h264_aac_mp4`) for a vendor export that is already
a standard, FFmpeg-readable container — currently used for Hikvision's
exported clips: unlike CP Plus's proprietary CPAV container, a Hikvision
export is (once its leading "IMKH" header is skipped — which FFmpeg's own
demuxer probing already does on its own) a standard MPEG-2 Program Stream
FFmpeg can demux directly, so no vendor-specific NAL-record reassembly
step exists between the evidence and FFmpeg (see
`app.adapters.hikvision.parser` for the real-evidence basis of that
claim). These two read directly from the *original* evidence file — the
only pair in this module that does. This module never opens the input
path for writing — reading it is the only access these two functions
perform, consistent with original evidence remaining immutable.
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


#: A Hikvision export's audio stream is G.711 mu-law (`pcm_mulaw`) — not a
#: codec the ISO/IEC 14496-14 MP4 muxer registers a tag for. Confirmed
#: empirically: `ffmpeg -c copy` against real evidence fails at the mux
#: step with "Could not find tag for codec pcm_mulaw in stream #1, codec
#: not currently supported in container" / "Could not write header
#: (incorrect codec parameters?)". AAC is therefore a forced, lossy
#: transcode of the audio track — never presented as a byte-preserved
#: original — while the video track is still a pure `-c:v copy` (the
#: original compressed HEVC bytes, byte-for-byte, exactly like
#: `mux_hevc_annexb_to_mp4` above for CP Plus).
_HIKVISION_DEFAULT_AUDIO_BITRATE = "64k"


def remux_container_to_mp4(
    source_path: Path,
    output_path: Path,
    *,
    audio_bitrate: str = _HIKVISION_DEFAULT_AUDIO_BITRATE,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> FFmpegResult:
    """Remux a Hikvision exported clip directly into a standard ISOBMFF MP4.

    Reads `source_path` directly — this is the ONLY function in this
    module that takes the *original preserved evidence* file as input
    rather than an already-produced derived elementary stream, because a
    Hikvision export needs no vendor-specific record reassembly first (see
    module docstring). FFmpeg opens `source_path` read-only; nothing here
    writes to it.

    Video is `-c:v copy` (byte-preserved, forensically authoritative — the
    original compressed HEVC frames, unchanged). Audio is transcoded to
    AAC (see `_HIKVISION_DEFAULT_AUDIO_BITRATE`'s docstring for why a
    direct copy is not possible into an MP4 container) — callers must
    treat the produced audio track as a lossy derivative, never as
    byte-preserved original evidence, and should record that distinction
    in provenance metadata.

    Args:
        source_path: Path to the original, preserved Hikvision export
            evidence file. Never modified.
        output_path: Destination `.mp4` path. Overwritten if it already
            exists (always a fresh derived-artifact path prepared by the
            caller, never preserved evidence).
        audio_bitrate: FFmpeg `-b:a` value for the AAC transcode.
        timeout: Maximum seconds to allow FFmpeg to run.

    Returns:
        An `FFmpegResult`. Never raises for an FFmpeg-side failure (e.g. a
        genuinely truncated/corrupted source) — callers inspect
        `ok`/`stderr`; a non-fatal mid-stream decode warning (e.g. one
        corrupt PS packet) still typically produces a usable, `ok=True`
        result with the warning visible in `stderr`, which callers should
        surface rather than discard.

    Raises:
        FileNotFoundError: If the configured FFmpeg executable itself is
            missing.
    """
    return run_ffmpeg(
        [
            "-y",
            "-i",
            str(source_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        timeout=timeout,
    )


def transcode_container_to_h264_aac_mp4(
    source_path: Path,
    output_path: Path,
    *,
    crf: int = 23,
    preset: str = "veryfast",
    audio_bitrate: str = _HIKVISION_DEFAULT_AUDIO_BITRATE,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> FFmpegResult:
    """Transcode a Hikvision exported clip to an H.264/AAC MP4 preview.

    Reads `source_path` (the original evidence) directly, same as
    `remux_container_to_mp4`. Both video and audio are re-encoded
    here — this is purely a browser-guaranteed-playable preview, never a
    substitute for the `-c:v copy` master `remux_container_to_mp4`
    produces.

    Args:
        source_path: Path to the original, preserved Hikvision export
            evidence file. Never modified.
        output_path: Destination `.mp4` path. Overwritten if it exists.
        crf: x264 constant-rate-factor quality setting.
        preset: x264 encoding-speed preset.
        audio_bitrate: FFmpeg `-b:a` value for the AAC transcode.
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
            "-i",
            str(source_path),
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        timeout=timeout,
    )
