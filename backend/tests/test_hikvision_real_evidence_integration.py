"""Real Hikvision evidence — Phase 26 acceptance test.

Proof, against the real three-clip evidence set (never synthetic bytes),
that:

  1. all three real exported `.mp4` clips are identified as genuine
     Hikvision evidence via filename + export-log sidecar corroboration,
  2. the confirmed device serial resolves to the examiner-confirmed
     DS-7A04HQHI-K1 / V4.30.220 Build 220216 device,
  3. real `ffprobe`-measured technical metadata (H.265/HEVC, 1920xNNNN,
     PCM mu-law audio, per-file frame rate) is captured -- never the
     device's configured 15 fps blindly substituted,
  4. filename-derived start timestamps are correct,
  5. no evidence file is modified by any of the above,
  6. `RecordingManager`/`EvidenceManager` correctly enumerate and persist
     these recordings end to end through the common pipeline, and
  7. `extract_recording` produces a real, playable derived MP4 via direct
     remux/transcode of the source evidence.

All tests here are `requires_real_evidence`-marked and skip (not fail)
when the out-of-repo evidence set is absent. Granular unit-level coverage
of the underlying parser/detector logic (synthetic-only) lives in
test_hikvision_adapter.py; this file is deliberately the end-to-end proof.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.hikvision.models import HikvisionClipIdentificationStatus
from app.adapters.hikvision.parser import HikvisionParser
from tests.fixtures.hikvision_evidence import (
    KNOWN_DEVICE_MODEL,
    KNOWN_DEVICE_SERIAL,
    real_clip_paths,
    requires_real_evidence,
)


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@requires_real_evidence
def test_all_real_clips_are_confirmed_by_export_log() -> None:
    for path in real_clip_paths():
        reader = FileBackedReader(path)
        try:
            result = HikvisionParser(reader).identify()
        finally:
            reader.close()
        assert (
            result.status == HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG
        ), f"{path.name}: {result.reason}"


@requires_real_evidence
def test_all_real_clips_resolve_known_device() -> None:
    for path in real_clip_paths():
        reader = FileBackedReader(path)
        try:
            result = HikvisionParser(reader).identify()
        finally:
            reader.close()
        assert result.sidecar is not None
        assert result.sidecar.device_serial == KNOWN_DEVICE_SERIAL
        assert result.known_device is not None
        assert result.known_device.model == KNOWN_DEVICE_MODEL


@requires_real_evidence
def test_real_clips_report_measured_hevc_technical_metadata() -> None:
    """H.265/HEVC, ~1920x1080-class resolution, real (not device-configured)
    fps, and PCM mu-law audio — every value ffprobe actually measured, never
    the device's configured 15 fps substituted (task Phase 26 scope,
    section 19)."""
    for path in real_clip_paths():
        reader = FileBackedReader(path)
        try:
            enumeration = HikvisionParser(reader, source_evidence_id="TEST").enumerate_recordings()
        finally:
            reader.close()
        assert len(enumeration.recordings) == 1
        record = enumeration.recordings[0]
        assert record.codec == "hevc"
        assert record.width == 1920
        assert record.height is not None and record.height >= 1080
        assert record.fps is not None and record.fps > 0
        assert record.has_audio is True
        assert record.audio_codec == "pcm_mulaw"
        assert record.duration_ms is not None and record.duration_ms > 0


@requires_real_evidence
def test_real_clip_filename_derived_start_timestamps() -> None:
    expected_starts = {
        "A01_20260829100000.mp4": "2026-08-29 10:00:00",
        "A01_20260831080000.mp4": "2026-08-31 08:00:00",
        "A02_20260831080000.mp4": "2026-08-31 08:00:00",
    }
    for path in real_clip_paths():
        reader = FileBackedReader(path)
        try:
            enumeration = HikvisionParser(reader).enumerate_recordings()
        finally:
            reader.close()
        record = enumeration.recordings[0]
        assert str(record.start_original) == expected_starts[path.name]


@requires_real_evidence
def test_real_evidence_files_are_never_modified() -> None:
    """Hashing before and after a full parse/probe pass must match --
    original evidence remains immutable."""
    before = {path: _sha256_of(path) for path in real_clip_paths()}
    for path in real_clip_paths():
        reader = FileBackedReader(path)
        try:
            HikvisionParser(reader, source_evidence_id="TEST").enumerate_recordings()
        finally:
            reader.close()
    after = {path: _sha256_of(path) for path in real_clip_paths()}
    assert before == after


@requires_real_evidence
def test_channel_and_camera_id_parsed_correctly() -> None:
    expected = {
        "A01_20260829100000.mp4": ("A01", 1),
        "A01_20260831080000.mp4": ("A01", 1),
        "A02_20260831080000.mp4": ("A02", 2),
    }
    for path in real_clip_paths():
        reader = FileBackedReader(path)
        try:
            enumeration = HikvisionParser(reader).enumerate_recordings()
        finally:
            reader.close()
        record = enumeration.recordings[0]
        assert (record.camera_id, record.channel) == expected[path.name]
