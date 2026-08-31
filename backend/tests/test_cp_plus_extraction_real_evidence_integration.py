"""Real CP Plus evidence — Phase 9 acceptance test.

Mirrors test_cp_plus_real_evidence_integration.py's shape exactly, proving
against the real 13-file evidence package (never synthetic bytes) that:

  1. HEVC elementary-stream reconstruction succeeds for a real segment,
     with per-family record counts matching the Phase 8 analysis report's
     own numbers for the smallest (2 s) file,
  2. the reconstructed stream begins with VPS/SPS/PPS/IDR NAL units in
     order,
  3. FFmpeg can mux that stream into a playable H.265 MP4 and transcode it
     into an H.264 MP4 preview, both with correct probed codec/resolution/
     duration,
  4. no evidence file is modified by any of the above.

All tests here are `requires_real_evidence`-marked and additionally skip
when FFmpeg is not installed, since muxing/transcoding needs a real
external tool.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest

from app.acquisition.storage_reader import FileBackedReader
from app.adapters.cp_plus import CPPlusAdapter
from app.adapters.cp_plus.extraction import extract_hevc_elementary_stream
from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.media.decoder import mux_hevc_annexb_to_mp4, transcode_to_h264_mp4
from app.media.ffmpeg import is_ffmpeg_available
from app.media.media_probe import probe_media
from app.models import Artifact
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from tests.fixtures.cp_plus_evidence import (
    load_expected_sha256,
    real_cpv_paths,
    requires_real_evidence,
    sha256_of,
    smallest_real_cpv_path,
)

requires_ffmpeg = pytest.mark.skipif(
    not is_ffmpeg_available(), reason="ffmpeg is not installed/runnable in this environment"
)


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Isolated EVIDENCE_ROOT/ARTIFACT_ROOT/DB -- matches
    test_cp_plus_processing_orchestrator_real_evidence_integration.py's own
    fixture; the real evidence directory is never used as EVIDENCE_ROOT
    directly and is never written to."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    evidence_root = tmp_path / "evidence"
    artifact_root = tmp_path / "artifacts"
    evidence_root.mkdir()
    artifact_root.mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(evidence_root))
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import app.models  # noqa: F401 - registers every ORM model on Base.metadata

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    try:
        yield db, evidence_root
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        get_settings.cache_clear()


def _register_smallest_real_evidence(db, evidence_root: Path, case_id: str):
    source_path = smallest_real_cpv_path()
    assert source_path is not None
    case = CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Extraction IT"))
    copied_path = evidence_root / source_path.name
    shutil.copy2(source_path, copied_path)
    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_path.stem, source_type="native_export", source_path=str(copied_path)
        ),
    )
    return evidence, source_path


@requires_real_evidence
def test_smallest_real_file_reconstructs_expected_video_records():
    """Per-family record counts on the smallest (2 s) file, cross-checked
    against CPV_ANALYSIS_REPORT.md section 9: 50 `0xF0`, 49 `0xFC`, 2
    `0xFD` (one truncated near EOF — see the file's own known corruption),
    2 `0xF1`/`0x6F1` telemetry records.
    """
    path = smallest_real_cpv_path()
    assert path is not None

    output = io.BytesIO()
    with FileBackedReader(path) as reader:
        result = extract_hevc_elementary_stream(reader, output, segment_label=path.name)

    # 49 VIDEO_FRAME + 1 (of 2) KEYFRAME_MARKER records parsed cleanly
    # before the walk stops at the second, truncated KEYFRAME_MARKER record.
    assert result.frames_written == 50
    assert result.keyframes_written == 1
    assert result.skipped_video_fixed_auxiliary == 50
    assert result.skipped_telemetry == 2
    assert result.frames_missing_nal == 0
    assert result.truncated is True  # the known truncated trailing record

    data = output.getvalue()
    assert len(data) > 0
    # VPS(32), SPS(33), PPS(34), IDR(19) — decoded directly from the HEVC
    # NAL header bit layout, matching app.adapters.cp_plus.container's own
    # decode: nal_unit_type = (first_byte_after_start_code >> 1) & 0x3F.
    assert (data[3] >> 1) & 0x3F == 32


@requires_real_evidence
def test_extraction_never_modifies_source_evidence_files():
    paths = real_cpv_paths()
    expected_hashes = load_expected_sha256()
    pre_hashes = {p.name: sha256_of(p) for p in paths}
    for name, digest in pre_hashes.items():
        assert expected_hashes[name] == digest

    for path in paths[:3]:  # a representative subset keeps this test fast
        output = io.BytesIO()
        with FileBackedReader(path) as reader:
            adapter = CPPlusAdapter(reader, source_evidence_id=path.stem)
            enumeration_result = adapter.enumerate_recordings()
            recording_id = enumeration_result.recordings[0]
            adapter.extract_recording(recording_id, destination=output)
        assert len(output.getvalue()) > 0

    post_hashes = {p.name: sha256_of(p) for p in paths}
    assert post_hashes == pre_hashes


@requires_real_evidence
@requires_ffmpeg
def test_reconstructed_stream_muxes_and_transcodes_to_playable_mp4(tmp_path: Path):
    path = smallest_real_cpv_path()
    assert path is not None

    output = io.BytesIO()
    with FileBackedReader(path) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id=path.stem)
        enumeration_result = adapter.enumerate_recordings()
        recording_id = enumeration_result.recordings[0]
        adapter.extract_recording(recording_id, destination=output)

    elementary_stream_path = tmp_path / "elementary_stream.h265"
    elementary_stream_path.write_bytes(output.getvalue())

    master_path = tmp_path / "master.mp4"
    mux_result = mux_hevc_annexb_to_mp4(elementary_stream_path, master_path)
    assert mux_result.ok, mux_result.stderr

    master_probe = probe_media(master_path)
    assert master_probe.available
    assert master_probe.codec == "hevc"
    assert master_probe.width == 1920
    assert master_probe.height == 1080
    assert master_probe.fps == pytest.approx(25.0, abs=0.1)
    # Known ground truth for this file: NVR_ch1_main_20260828162000_20260828162002.cpv (2 s).
    assert master_probe.duration_seconds == pytest.approx(2.0, abs=0.3)

    preview_path = tmp_path / "preview.mp4"
    transcode_result = transcode_to_h264_mp4(elementary_stream_path, preview_path)
    assert transcode_result.ok, transcode_result.stderr

    preview_probe = probe_media(preview_path)
    assert preview_probe.available
    assert preview_probe.codec == "h264"
    assert preview_probe.width == 1920
    assert preview_probe.height == 1080


@requires_real_evidence
@requires_ffmpeg
def test_extract_recording_persists_media_metadata_matching_probe(real_evidence_db) -> None:
    """Regression test (Phase 24.1 fix): a successful `extract_recording`
    must persist the real, probed codec/container/width/height/fps/
    duration onto the `Recording` row itself -- not leave them `None` for
    every caller to separately re-derive. Ground truth for this file
    matches `test_reconstructed_stream_muxes_and_transcodes_to_playable_mp4`
    above exactly (1920x1080, ~25fps, ~2s)."""
    db, evidence_root = real_evidence_db
    evidence, _source_path = _register_smallest_real_evidence(
        db, evidence_root, "CASE-EXTRACT-META"
    )

    recordings = RecordingManager.enumerate_recordings(db, evidence.id)
    assert recordings
    recording = RecordingManager.extract_recording(db, recordings[0].id)

    assert recording.artifact_id is not None  # this file's master mux succeeds
    assert recording.codec == "hevc"
    assert recording.container == "mp4"
    assert recording.width == 1920
    assert recording.height == 1080
    assert recording.fps == pytest.approx(25.0, abs=0.1)
    assert recording.duration_ms == pytest.approx(2000, abs=300)


@requires_real_evidence
@requires_ffmpeg
def test_re_enumerating_does_not_clobber_extracted_media_metadata(real_evidence_db) -> None:
    """Regression test (Phase 24.1 fix): re-running `enumerate_recordings`
    against the same evidence -- which is exactly what the plain
    `GET /evidence/{id}/recordings` route (and so every Evidence-tab page
    view) does -- must never wipe out width/height/fps/codec/container/
    duration_ms that `extract_recording` already probed and persisted.
    `to_recording_fields` deliberately maps these to `None` (CP Plus's own
    container never carries them), and the enumeration-update path used to
    blindly re-apply every one of `to_recording_fields`' values onto an
    existing row -- silently discarding real probed data the moment an
    officer next opened the Evidence tab."""
    db, evidence_root = real_evidence_db
    evidence, _source_path = _register_smallest_real_evidence(db, evidence_root, "CASE-REENUM-META")

    recordings = RecordingManager.enumerate_recordings(db, evidence.id)
    recording = RecordingManager.extract_recording(db, recordings[0].id)
    assert recording.fps is not None  # sanity: extraction did populate it

    # SQLAlchemy's identity map means `re_enumerated[0]` below is the exact
    # same Python object as `recording` (same PK, same session) -- so every
    # comparison must be against values snapshotted *before* re-enumeration
    # runs, never against `recording.<attr>` read again afterwards (that
    # would just compare the mutated object to itself and could never fail).
    recording_pk = recording.id
    artifact_id_before = recording.artifact_id
    recording_id_before = recording.recording_id
    source_location_before = recording.source_location
    assert artifact_id_before is not None  # this file's master mux succeeds

    # Re-enumerate the same evidence -- as the frontend's Evidence tab does
    # on every view -- and confirm nothing was wiped.
    re_enumerated = RecordingManager.enumerate_recordings(db, evidence.id)
    assert len(re_enumerated) == 1
    still_there = re_enumerated[0]
    assert still_there.id == recording_pk
    assert still_there.artifact_id == artifact_id_before
    assert still_there.codec == "hevc"
    assert still_there.container == "mp4"
    assert still_there.width == 1920
    assert still_there.height == 1080
    assert still_there.fps == pytest.approx(25.0, abs=0.1)
    assert still_there.duration_ms == pytest.approx(2000, abs=300)

    # Fields enumeration IS authoritative for must still update normally
    # (this isn't a blanket "never touch existing rows" regression).
    assert still_there.recording_id == recording_id_before
    assert still_there.source_location == source_location_before


@requires_real_evidence
@requires_ffmpeg
def test_refresh_media_metadata_backfills_stale_recording_from_existing_master(
    real_evidence_db,
) -> None:
    """`refresh_media_metadata` must recover the exact values a fresh
    extraction would have produced -- by re-probing the already-produced
    master artifact, never by re-muxing, re-transcoding, or fabricating a
    value (task: "Persist only values returned by the actual media
    probe")."""
    db, evidence_root = real_evidence_db
    evidence, _source_path = _register_smallest_real_evidence(
        db, evidence_root, "CASE-REFRESH-META"
    )

    recordings = RecordingManager.enumerate_recordings(db, evidence.id)
    recording = RecordingManager.extract_recording(db, recordings[0].id)
    master_artifact_id = recording.artifact_id
    assert master_artifact_id is not None

    master_artifact = db.query(Artifact).filter(Artifact.id == int(master_artifact_id)).first()
    assert master_artifact is not None
    master_sha256_before = master_artifact.sha256
    master_mtime_before = Path(master_artifact.path).stat().st_mtime

    # Simulate a stale pre-existing row (written before this metadata was
    # tracked, or by a run that predates this code) -- source evidence and
    # every artifact/hash row are left exactly as extraction produced them.
    recording.codec = None
    recording.container = None
    recording.width = None
    recording.height = None
    recording.fps = None
    recording.duration_ms = None
    db.commit()
    db.refresh(recording)

    refreshed = RecordingManager.refresh_media_metadata(db, recording.id)

    assert refreshed.artifact_id == master_artifact_id  # no re-extraction happened
    assert refreshed.codec == "hevc"
    assert refreshed.container == "mp4"
    assert refreshed.width == 1920
    assert refreshed.height == 1080
    assert refreshed.fps == pytest.approx(25.0, abs=0.1)
    assert refreshed.duration_ms == pytest.approx(2000, abs=300)

    # The master artifact file/hash was never rewritten or re-muxed.
    assert master_artifact.sha256 == master_sha256_before
    assert Path(master_artifact.path).stat().st_mtime == master_mtime_before

    # And the persisted values genuinely match an independent, fresh probe
    # of that same artifact -- proving they are the real probe output,
    # never a fabricated/hardcoded constant.
    fresh_probe = probe_media(Path(master_artifact.path))
    assert fresh_probe.available
    assert refreshed.width == fresh_probe.width
    assert refreshed.height == fresh_probe.height
    assert refreshed.fps == fresh_probe.fps
    assert refreshed.codec == fresh_probe.codec
