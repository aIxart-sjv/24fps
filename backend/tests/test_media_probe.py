"""Tests for FFprobe-based media inspection (app/media/media_probe.py), Phase 9."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.media.ffmpeg import is_ffmpeg_available, run_ffmpeg
from app.media.media_probe import probe_media

requires_ffmpeg = pytest.mark.skipif(
    not is_ffmpeg_available(), reason="ffmpeg is not installed/runnable in this environment"
)


def test_probe_media_on_nonexistent_file_reports_unavailable():
    result = probe_media(Path("/no/such/file.mp4"))
    assert result.available is False
    assert result.codec is None
    assert result.warnings


def test_probe_media_on_non_media_file_reports_unavailable(tmp_path: Path):
    text_file = tmp_path / "not_a_video.txt"
    text_file.write_text("this is definitely not a video file")
    result = probe_media(text_file)
    assert result.available is False


@requires_ffmpeg
def test_probe_media_reports_correct_dimensions_and_duration(tmp_path: Path):
    output = tmp_path / "tiny.mp4"
    result = run_ffmpeg(
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x48:d=1:r=10",
            "-c:v",
            "libx264",
            str(output),
        ]
    )
    assert result.ok, result.stderr

    probe = probe_media(output)
    assert probe.available is True
    assert probe.codec == "h264"
    assert probe.width == 64
    assert probe.height == 48
    assert probe.duration_seconds is not None
    assert probe.duration_seconds == pytest.approx(1.0, abs=0.2)


def _make_video_audio(path: Path, *, video_delay: float) -> None:
    """A tiny clip whose video track starts `video_delay` s after the audio track."""
    result = run_ffmpeg(
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2:sample_rate=8000",
            "-itsoffset",
            str(video_delay),
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x64:rate=10:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "32k",
            str(path),
        ]
    )
    assert result.ok, result.stderr


@requires_ffmpeg
def test_probe_media_reports_video_start_offset_when_audio_leads(tmp_path: Path):
    """Regression (Hikvision exports): the source's audio leads the video by ~0.2 s and the
    derived MP4 keeps that, so a browser shows frame N at N/fps + offset, not N/fps."""
    clip = tmp_path / "audio_leads.mp4"
    _make_video_audio(clip, video_delay=0.25)
    result = probe_media(clip)
    assert result.available
    assert result.video_start_offset_seconds is not None
    assert 0.2 < result.video_start_offset_seconds < 0.5


@requires_ffmpeg
def test_probe_media_video_start_offset_is_zero_for_video_only_media(tmp_path: Path):
    clip = tmp_path / "video_only.mp4"
    result = run_ffmpeg(
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x64:rate=10:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ]
    )
    assert result.ok, result.stderr
    probed = probe_media(clip)
    assert probed.video_start_offset_seconds == pytest.approx(0.0, abs=1e-6)


@requires_ffmpeg
def test_probe_media_count_packets_measures_frame_rate_independently_of_the_header(tmp_path: Path):
    clip = tmp_path / "ten_fps.mp4"
    result = run_ffmpeg(
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x64:rate=10:duration=3",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ]
    )
    assert result.ok, result.stderr
    plain = probe_media(clip)
    counted = probe_media(clip, count_packets=True)
    assert plain.video_packet_count is None and plain.measured_fps is None  # opt-in only
    assert counted.video_packet_count == 30
    assert counted.measured_fps == pytest.approx(10.0, rel=0.02)
    assert counted.r_frame_rate == pytest.approx(10.0)
