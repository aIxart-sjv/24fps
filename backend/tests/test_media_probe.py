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
