"""Hikvision through the REAL investigator workflow -- regression coverage for the
user-reported "Hikvision integration does not actually work" failure.

WHY THIS FILE EXISTS
--------------------
Phase 26's first delivery was validated only by tests that copied a clip into a
scratch evidence root under its ORIGINAL filename, next to its `.txt` export-log
sidecar, and registered it by path. The real application never does that: the
browser UI uploads exactly ONE file through `POST /cases/{id}/evidence/upload`,
which stores it as `<evidence_id>_<original filename>` and has no way to place a
sidecar beside it. Identification (which required an exactly-anchored filename
AND a same-stem sidecar) therefore rejected every real upload, enumeration was
`skipped`, and nothing downstream (extraction, recovery, timeline, playback,
seek, AI) ever ran -- which the user's own database showed for three separate
attempts (`vendor = NULL`, `enumeration = skipped`, zero recordings).

These tests drive the same HTTP routes the frontend uses, with the real
evidence bytes, so that class of gap cannot pass CI again. They skip (never
fail) when the out-of-repo evidence set or FFmpeg is absent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.case_manager import CaseManager
from app.media.ffmpeg import is_ffmpeg_available
from app.schemas.case import CaseCreateRequest
from tests.fixtures.hikvision_evidence import EVIDENCE_DIR, requires_real_evidence

requires_ffmpeg = pytest.mark.skipif(
    not is_ffmpeg_available(), reason="ffmpeg is not installed/runnable in this environment"
)

#: Smallest of the three real clips -- keeps the FFmpeg remux+transcode cheap.
_CLIP = "A01_20260831080000.mp4"
#: Ground truth measured directly from the real files (NOT from any header) with
#: `ffprobe -count_packets`: this clip has 6700 video packets over 446.55 s
#: (=15.004 fps); the other two clips measure 9016 packets / 601.0 s (=15.001 fps).
#: Meanwhile the container DECLARES avg_frame_rate=30/1 and r_frame_rate=25/1 for all
#: three -- both wrong. The recorder's configured rate is 15 fps.
_EXPECTED_MEASURED_FPS = 15.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _upload_like_the_ui(test_client, headers, case_pk: int, evidence_id: str, clip: Path) -> dict:
    """Exactly what `frontend/src/lib/api.ts` does: ONE multipart file, no sidecar."""
    with clip.open("rb") as handle:
        resp = test_client.post(
            f"/api/v1/cases/{case_pk}/evidence/upload",
            data={"evidence_id": evidence_id, "source_type": "native_export"},
            files={"file": (clip.name, handle, "application/octet-stream")},
            headers=headers,
        )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _process(test_client, headers, case_pk: int) -> dict:
    resp = test_client.post(f"/api/v1/cases/{case_pk}/process", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _stage_status(run: dict) -> dict[str, str]:
    return {stage["job_type"]: stage["status"] for stage in run["stages"]}


@pytest.fixture(scope="module")
def processed(tmp_path_factory):
    """Upload the real clip the way the UI does and run automatic processing ONCE.

    Module-scoped (own in-memory DB, own EVIDENCE/ARTIFACT/REPORT roots, own
    app + client) because the pipeline includes an FFmpeg remux and an H.264
    transcode -- running it per test made this file take minutes.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401 - registers every ORM model on Base.metadata
    from app.core.auth_manager import AuthManager
    from app.main import create_app
    from app.models import UserRole
    from app.storage.db import Base, get_db

    if not (EVIDENCE_DIR / _CLIP).is_file():
        pytest.skip(f"real Hikvision evidence not found at {EVIDENCE_DIR}")
    if not is_ffmpeg_available():
        pytest.skip("ffmpeg is not installed/runnable in this environment")

    base = tmp_path_factory.mktemp("hik_ui_workflow")
    monkeypatch = pytest.MonkeyPatch()
    for name in ("evidence", "artifacts", "reports"):
        (base / name).mkdir()
    monkeypatch.setenv("EVIDENCE_ROOT", str(base / "evidence"))
    monkeypatch.setenv("ARTIFACT_ROOT", str(base / "artifacts"))
    monkeypatch.setenv("REPORT_ROOT", str(base / "reports"))
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    db = session_factory()
    try:
        AuthManager.create_user(
            db,
            username="hik_admin",
            display_name="Hik Admin",
            password="password123",
            role=UserRole.ADMIN,
        )
        case = CaseManager.create_case(db, CaseCreateRequest(case_id="HIK-UI-1", name="UI path"))
        case_pk = case.id
    finally:
        db.close()

    login = client.post(
        "/api/v1/auth/login", json={"username": "hik_admin", "password": "password123"}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    clip = EVIDENCE_DIR / _CLIP
    before = _sha256(clip)
    evidence = _upload_like_the_ui(client, headers, case_pk, "EV-HIK-UI-1", clip)
    run = _process(client, headers, case_pk)
    try:
        yield {
            "session_factory": session_factory,
            "client": client,
            "headers": headers,
            "case_pk": case_pk,
            "evidence": evidence,
            "run": run,
            "clip": clip,
            "clip_hash_before": before,
        }
    finally:
        app.dependency_overrides.clear()
        monkeypatch.undo()
        get_settings.cache_clear()
        engine.dispose()


@requires_real_evidence
@requires_ffmpeg
def test_stored_upload_really_has_the_evidence_id_prefix_and_no_sidecar(processed):
    """Pins the precondition that broke Phase 26: the stored name is prefixed and
    nothing but the clip exists next to it. If this ever changes, revisit the fix."""
    stored = Path(processed["evidence"]["source_path"])
    assert stored.name == f"EV-HIK-UI-1_{_CLIP}"
    assert sorted(p.name for p in stored.parent.iterdir()) == [stored.name]


@requires_real_evidence
@requires_ffmpeg
def test_ui_upload_is_identified_as_hikvision_and_enumerated(processed):
    c, h, ev = processed["client"], processed["headers"], processed["evidence"]

    stages = _stage_status(processed["run"])
    assert stages["identification"] == "completed"
    assert stages["enumeration"] == "completed", (
        "enumeration was skipped -- a real UI-uploaded Hikvision clip was not recognized; "
        f"stages={stages}"
    )
    assert stages["extraction"] == "completed"

    device = c.get(f"/api/v1/evidence/{ev['id']}/device", headers=h).json()
    assert device["vendor"] == "Hikvision"
    # Model/serial/firmware must NOT be claimed from the MP4 alone (no sidecar was uploaded).
    assert device["model"] is None
    assert device["serial_number"] is None
    assert device["firmware"] is None
    assert device["identification_method"] == "hikvision_container_header"
    assert 0.0 < device["confidence"] < 1.0, "header-only identification must not claim certainty"

    recordings = c.get(f"/api/v1/evidence/{ev['id']}/recordings", headers=h).json()
    assert len(recordings) == 1
    rec = recordings[0]
    # Channel / start come from the ORIGINAL filename, recovered by stripping the
    # `<evidence_id>_` prefix the upload route added.
    assert (rec["camera_id"], rec["channel"]) == ("A01", 1)
    assert rec["start_original"].startswith("2026-08-31T08:00:00")
    assert rec["recording_id"] != _CLIP.removesuffix(
        ".mp4"
    ), "recording_id must be evidence-scoped so the same clip in two cases cannot collide"


@requires_real_evidence
@requires_ffmpeg
def test_media_fields_are_measured_and_survive_re_enumeration(processed):
    """The `/recordings` route re-enumerates on every Evidence-tab view. It must not
    overwrite what extraction established (container mp4, ~15 fps) with the source
    header's wrong values (declared avg 30 / r 25)."""
    c, h, ev = processed["client"], processed["headers"], processed["evidence"]
    first = c.get(f"/api/v1/evidence/{ev['id']}/recordings", headers=h).json()[0]
    second = c.get(f"/api/v1/evidence/{ev['id']}/recordings", headers=h).json()[0]

    assert first["codec"] == "hevc"
    assert (first["width"], first["height"]) == (1920, 1088)  # as MEASURED, not "corrected"
    assert first["container"] == "mp4"  # the playable derived master's container
    assert first["fps"] == pytest.approx(_EXPECTED_MEASURED_FPS, abs=0.1)
    assert first["artifact_id"] is not None
    for field in ("codec", "container", "width", "height", "fps", "duration_ms", "artifact_id"):
        assert second[field] == first[field], f"re-enumeration clobbered {field!r}"


@requires_real_evidence
@requires_ffmpeg
def test_source_fps_discrepancy_is_preserved_not_hidden(processed):
    c, h, ev = processed["client"], processed["headers"], processed["evidence"]
    rec = c.get(f"/api/v1/evidence/{ev['id']}/recordings", headers=h).json()[0]
    meta = {
        m["key"]: m["value"]
        for m in c.get(f"/api/v1/recordings/{rec['id']}/metadata", headers=h).json()
    }
    assert float(meta["source_declared_avg_frame_rate"]) == pytest.approx(30.0)
    assert float(meta["source_declared_r_frame_rate"]) == pytest.approx(25.0)
    assert float(meta["source_measured_fps"]) == pytest.approx(_EXPECTED_MEASURED_FPS, abs=0.1)
    assert "source_frame_rate_discrepancy" in meta


@requires_real_evidence
@requires_ffmpeg
def test_extraction_warnings_are_real_warnings_not_an_ffmpeg_banner(processed):
    c, h, ev = processed["client"], processed["headers"], processed["evidence"]
    rec = c.get(f"/api/v1/evidence/{ev['id']}/recordings", headers=h).json()[0]
    meta = {
        m["key"]: m["value"]
        for m in c.get(f"/api/v1/recordings/{rec['id']}/metadata", headers=h).json()
    }
    assert meta["extraction_status"] == "successful"
    blob = meta["extraction_warnings"]
    for noise in ("Stream mapping", "Press [q]", "Input #0", "Output #0", "Metadata:"):
        assert noise not in blob, f"ffmpeg progress/banner text leaked into warnings: {noise!r}"


@requires_real_evidence
@requires_ffmpeg
def test_recovery_is_truthful_for_exported_media(processed):
    """No CP Plus engine (ADIT/CPAV carving, fragment counts) may be applied to a
    Hikvision clip, and nothing may be reported as recovered."""
    c, h, ev = processed["client"], processed["headers"], processed["evidence"]
    results = c.get(f"/api/v1/evidence/{ev['id']}/recovery-results", headers=h).json()
    assert len(results) == 1
    result = results[0]
    assert result["status"] == "unsupported"
    assert "not_supported_for_exported_media" in result["notes"]
    for cp_plus_only in ("ADIT", "CPAV", "CPV_ANALYSIS_REPORT"):
        assert cp_plus_only not in result["notes"], f"CP Plus text leaked: {cp_plus_only}"
    assert result["artifact_id"] is None
    assert result["fragments_found"] in (None, 0)
    assert result["confidence"] is None
    assert result["frames_recovered"] in (None, 0)


@requires_real_evidence
@requires_ffmpeg
def test_timestamp_source_is_classified_for_hikvision(processed):
    c, h, ev = processed["client"], processed["headers"], processed["evidence"]
    rec = c.get(f"/api/v1/evidence/{ev['id']}/recordings", headers=h).json()[0]
    meta = {
        m["key"]: m["value"]
        for m in c.get(f"/api/v1/recordings/{rec['id']}/metadata", headers=h).json()
    }
    assert meta["timestamp_normalization_source"] == "filename_derived"
    assert "no timestamp-source classification" not in meta.get("timestamp_source_note", "")
    # Recorder timezone is NOT knowable from an MP4-only upload: normalization must stay
    # honestly unresolved rather than guess one.
    assert meta["timestamp_normalization_status"] == "unknown"
    assert rec["start_normalized"] is None


@requires_real_evidence
@requires_ffmpeg
def test_derived_playback_media_streams_with_byte_ranges(processed):
    c, h, ev = processed["client"], processed["headers"], processed["evidence"]
    rec = c.get(f"/api/v1/evidence/{ev['id']}/recordings", headers=h).json()[0]
    meta = {
        m["key"]: m["value"]
        for m in c.get(f"/api/v1/recordings/{rec['id']}/metadata", headers=h).json()
    }
    preview_id = int(meta["preview_artifact_id"])
    resp = c.get(f"/api/v1/artifacts/{preview_id}/download", headers={**h, "Range": "bytes=0-99"})
    assert resp.status_code == 206
    assert resp.headers["accept-ranges"] == "bytes"
    assert resp.headers["content-type"] == "video/mp4"
    assert len(resp.content) == 100


@requires_real_evidence
@requires_ffmpeg
def test_original_evidence_and_upload_copy_are_never_modified(processed):
    clip: Path = processed["clip"]
    assert _sha256(clip) == processed["clip_hash_before"]
    stored = Path(processed["evidence"]["source_path"])
    assert _sha256(stored) == processed["clip_hash_before"]


@requires_real_evidence
@requires_ffmpeg
def test_processing_findings_do_not_claim_hikvision_is_unsupported(processed):
    c, h, case_pk = processed["client"], processed["headers"], processed["case_pk"]
    findings = c.get(f"/api/v1/cases/{case_pk}/findings", headers=h).json()
    assert not [f for f in findings if f["finding_type"] == "unsupported_format"], json.dumps(
        [f["title"] for f in findings]
    )


@requires_real_evidence
@requires_ffmpeg
def test_preview_video_start_offset_is_measured_from_the_served_artifact(processed):
    """The real clips' audio leads video by ~0.1-0.2 s, so the served preview's video track starts
    after the container timeline's zero. A browser shows frame N at N/fps + offset (measured in
    Brave: seeking to N/fps alone lands 4 frames = 0.2 s early), so the backend must record it."""
    import subprocess

    c, h, ev = processed["client"], processed["headers"], processed["evidence"]
    rec = c.get(f"/api/v1/evidence/{ev['id']}/recordings", headers=h).json()[0]
    meta = {
        m["key"]: m["value"]
        for m in c.get(f"/api/v1/recordings/{rec['id']}/metadata", headers=h).json()
    }
    stored = float(meta["preview_video_start_offset_seconds"])
    assert stored > 0.05, "expected a real non-zero offset on this evidence"

    # Independent check: ask ffprobe about the very file the player downloads.
    artifact = c.get(f"/api/v1/artifacts/{int(meta['preview_artifact_id'])}", headers=h).json()
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=start_time",
            "-of",
            "csv=p=0",
            artifact["path"],
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert stored == pytest.approx(float(out), abs=0.001)  # container start_time is 0 here


@requires_real_evidence
@requires_ffmpeg
def test_header_only_upload_reports_no_channel_count(processed):
    """A bare MP4 cannot prove how many channels the recorder has."""
    c, h, ev = processed["client"], processed["headers"], processed["evidence"]
    device = c.get(f"/api/v1/evidence/{ev['id']}/device", headers=h).json()
    assert device["channel_count"] is None


@requires_real_evidence
@requires_ffmpeg
def test_extraction_provenance_records_operation_parameters_and_adapter_version(processed):
    """Provenance: what was done to the preserved source, with which adapter version -- and it
    must disclose that only the video is byte-preserved (audio is lossy AAC)."""
    from app.adapters.hikvision.parser import PARSER_VERSION

    c, h, ev = processed["client"], processed["headers"], processed["evidence"]
    rec = c.get(f"/api/v1/evidence/{ev['id']}/recordings", headers=h).json()[0]
    meta = {
        m["key"]: m["value"]
        for m in c.get(f"/api/v1/recordings/{rec['id']}/metadata", headers=h).json()
    }
    params = json.loads(meta["extraction_parameters"])
    assert params["adapter"] == "Hikvision"
    assert params["adapter_version"] == PARSER_VERSION == meta["parser_version"]
    assert "-c:v copy" in params["master_artifact"]["ffmpeg_args"]
    assert "original HEVC bytes preserved" in params["master_artifact"]["video"]
    assert "lossy" in params["master_artifact"]["audio"]
    assert "NOT the forensic record" in params["preview_artifact"]["operation"]
    assert meta["ffmpeg_version"].startswith("ffmpeg version")


@requires_real_evidence
@requires_ffmpeg
def test_hikvision_case_can_be_anchored_and_verified_by_the_existing_blockchain_manager(processed):
    """The Hikvision case's audit chain is an ordinary Phase 16 chain, so the existing Phase 17
    anchoring works on it unchanged. Uses the in-memory `LocalTestBlockchainProvider` -- this is NOT
    a real blockchain transaction (the deployment's BLOCKCHAIN_PROVIDER=none), and no video is
    anchored: only the cryptographic audit-state hash."""
    from app.blockchain.provider import LocalTestBlockchainProvider
    from app.blockchain.verification import AnchorVerificationOutcome
    from app.core.blockchain_manager import BlockchainManager

    db = processed["session_factory"]()
    try:
        provider = LocalTestBlockchainProvider()
        anchor = BlockchainManager.create_anchor(
            db, case_id=processed["case_pk"], provider=provider, reason="hikvision-regression"
        )
        assert len(anchor.audit_state_hash) == 64  # a SHA-256 hex digest, not media
        result = BlockchainManager.verify_anchor(db, anchor_id=anchor.id, provider=provider)
        assert result.valid and result.outcome == AnchorVerificationOutcome.VALID
        assert result.chain_valid
    finally:
        db.close()
