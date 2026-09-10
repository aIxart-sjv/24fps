"""Real Hikvision evidence, through the common RecordingManager pipeline
(Phase 26 acceptance test).

Mirrors test_cp_plus_extraction_real_evidence_integration.py's isolated-
EVIDENCE_ROOT fixture shape, proving against real evidence (never
synthetic bytes) that:

  1. `RecordingManager.enumerate_recordings` identifies a real Hikvision
     export end to end and persists a `Recording` row with real
     `ffprobe`-measured technical metadata and Hikvision-specific
     provenance metadata (device serial/model/firmware, export-log path),
  2. `EvidenceManager.confirm_vendor`/`confirm_device_serial` correctly
     record "Hikvision" and the confirmed serial on `Device`,
  3. `RecordingManager.extract_recording` produces a real, playable
     derived MP4 via direct remux from the source evidence (no elementary-
     stream reconstruction step, unlike CP Plus),
  4. re-running enumeration after extraction never clobbers the
     already-probed technical metadata with placeholders (the same
     `_MEDIA_PROBE_OWNED_FIELDS` guarantee CP Plus's own regression test
     covers),
  5. no evidence file (including its sidecar) is modified by any of the
     above.

All tests here are `requires_real_evidence`-marked and skip when the
out-of-repo evidence set is absent; extraction tests additionally skip
when FFmpeg is not installed.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.media.ffmpeg import is_ffmpeg_available
from app.models import RecordingMetadata
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.db import Base
from tests.fixtures.hikvision_evidence import (
    EVIDENCE_DIR,
    KNOWN_DEVICE_MODEL,
    KNOWN_DEVICE_SERIAL,
    requires_real_evidence,
)

requires_ffmpeg = pytest.mark.skipif(
    not is_ffmpeg_available(), reason="ffmpeg is not installed/runnable in this environment"
)

_SMALLEST_CLIP = "A01_20260831080000.mp4"


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture
def real_evidence_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Isolated EVIDENCE_ROOT/ARTIFACT_ROOT/DB -- the real evidence
    directory is never used as EVIDENCE_ROOT directly and is never
    written to; both the clip and its same-stem sidecar are copied into
    the isolated root so the sidecar-lookup identification path (which
    looks for a same-stem file next to the registered evidence path) has
    what it needs."""
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


def _register_real_clip(db, evidence_root: Path, case_id: str, clip_name: str = _SMALLEST_CLIP):
    source_path = EVIDENCE_DIR / clip_name
    sidecar_path = EVIDENCE_DIR / f"{source_path.stem}.txt"
    assert source_path.is_file()
    assert sidecar_path.is_file()

    case = CaseManager.create_case(
        db, CaseCreateRequest(case_id=case_id, name="Hikvision Extraction IT")
    )
    copied_clip = evidence_root / source_path.name
    copied_sidecar = evidence_root / sidecar_path.name
    shutil.copy2(source_path, copied_clip)
    shutil.copy2(sidecar_path, copied_sidecar)

    evidence = EvidenceManager.register_evidence(
        db,
        case.id,
        EvidenceCreateRequest(
            evidence_id=copied_clip.stem, source_type="native_export", source_path=str(copied_clip)
        ),
    )
    return evidence, source_path, sidecar_path


def _metadata_value(db, recording_id: int, key: str) -> str | None:
    entry = (
        db.query(RecordingMetadata)
        .filter(RecordingMetadata.recording_id == recording_id, RecordingMetadata.key == key)
        .first()
    )
    return entry.value if entry is not None else None


@requires_real_evidence
def test_enumerate_recordings_persists_hikvision_recording(real_evidence_db):
    db, evidence_root = real_evidence_db
    evidence, _source, _sidecar = _register_real_clip(db, evidence_root, "HIK-ENUM-1")

    recordings = RecordingManager.enumerate_recordings(db, evidence.id)

    assert len(recordings) == 1
    recording = recordings[0]
    assert recording.codec == "hevc"
    assert recording.width == 1920
    assert recording.camera_id == "A01"
    assert recording.channel == 1

    assert _metadata_value(db, recording.id, "vendor") == "Hikvision"
    assert _metadata_value(db, recording.id, "hikvision_device_serial") == KNOWN_DEVICE_SERIAL
    assert _metadata_value(db, recording.id, "hikvision_device_model") == KNOWN_DEVICE_MODEL

    db.refresh(evidence)
    assert evidence.device is not None
    assert evidence.device.vendor == "Hikvision"
    assert evidence.device.serial_number == KNOWN_DEVICE_SERIAL


@requires_real_evidence
@requires_ffmpeg
def test_extract_recording_produces_playable_master_mp4(real_evidence_db):
    db, evidence_root = real_evidence_db
    evidence, source_path, sidecar_path = _register_real_clip(db, evidence_root, "HIK-EXTRACT-1")

    pre_clip_hash = _sha256_of(source_path)
    pre_sidecar_hash = _sha256_of(sidecar_path)

    recordings = RecordingManager.enumerate_recordings(db, evidence.id)
    recording = recordings[0]

    extracted = RecordingManager.extract_recording(db, recording.id)

    status = _metadata_value(db, extracted.id, "extraction_status")
    assert status == "successful", _metadata_value(db, extracted.id, "extraction_warnings")
    assert extracted.artifact_id is not None
    assert extracted.container == "mp4"
    assert extracted.codec is not None

    # Re-running enumeration must never clobber extraction's own probed
    # values with placeholders (Phase 24.1 regression class).
    RecordingManager.enumerate_recordings(db, evidence.id)
    db.refresh(extracted)
    assert extracted.codec is not None
    assert extracted.width == 1920

    assert _sha256_of(source_path) == pre_clip_hash
    assert _sha256_of(sidecar_path) == pre_sidecar_hash
