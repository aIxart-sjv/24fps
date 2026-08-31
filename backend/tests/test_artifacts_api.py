"""Tests for app/api/routes/artifacts.py (Phase 23)."""

from __future__ import annotations

from pathlib import Path

from app.core.case_manager import CaseManager
from app.models import Artifact, Evidence
from app.schemas.case import CaseCreateRequest


def _make_evidence(db, case_id: str = "CASE-ART-1") -> Evidence:
    case = CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Artifact API test"))
    evidence = Evidence(evidence_id=f"{case_id}-EV", case_id=case.id, source_type="native_export")
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def test_get_artifact_metadata(
    test_db, test_client, tmp_path: Path, make_authenticated_headers
) -> None:
    evidence = _make_evidence(test_db)
    path = tmp_path / "preview.mp4"
    path.write_bytes(b"fake mp4 bytes")
    artifact = Artifact(
        evidence_id=evidence.id,
        artifact_type="cp_plus_h264_preview_mp4",
        path=str(path),
        size_bytes=path.stat().st_size,
        sha256="deadbeef",
    )
    test_db.add(artifact)
    test_db.commit()
    test_db.refresh(artifact)

    resp = test_client.get(f"/api/v1/artifacts/{artifact.id}", headers=make_authenticated_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["artifact_type"] == "cp_plus_h264_preview_mp4"
    assert body["sha256"] == "deadbeef"


def test_download_artifact_streams_file_bytes(
    test_db, test_client, tmp_path: Path, make_authenticated_headers
) -> None:
    evidence = _make_evidence(test_db, "CASE-ART-2")
    path = tmp_path / "preview2.mp4"
    path.write_bytes(b"\x00\x01\x02real-bytes-here")
    artifact = Artifact(
        evidence_id=evidence.id,
        artifact_type="cp_plus_h264_preview_mp4",
        path=str(path),
        size_bytes=path.stat().st_size,
    )
    test_db.add(artifact)
    test_db.commit()
    test_db.refresh(artifact)

    resp = test_client.get(
        f"/api/v1/artifacts/{artifact.id}/download", headers=make_authenticated_headers()
    )
    assert resp.status_code == 200
    assert resp.content == path.read_bytes()
    assert resp.headers["content-type"] == "video/mp4"


def test_download_artifact_streams_via_query_token_fallback(
    test_db, test_client, tmp_path: Path, make_authenticated_headers
) -> None:
    """The `<video src>` streaming path (Phase 25's
    `get_current_user_from_header_or_query`): no `Authorization` header,
    just `?token=`."""
    evidence = _make_evidence(test_db, "CASE-ART-5")
    path = tmp_path / "preview5.mp4"
    path.write_bytes(b"query-token-bytes")
    artifact = Artifact(
        evidence_id=evidence.id, artifact_type="cp_plus_h264_preview_mp4", path=str(path)
    )
    test_db.add(artifact)
    test_db.commit()
    test_db.refresh(artifact)

    headers = make_authenticated_headers()
    raw_token = headers["Authorization"].removeprefix("Bearer ")

    resp = test_client.get(f"/api/v1/artifacts/{artifact.id}/download?token={raw_token}")
    assert resp.status_code == 200
    assert resp.content == path.read_bytes()

    # No token at all -> still rejected.
    anon_resp = test_client.get(f"/api/v1/artifacts/{artifact.id}/download")
    assert anon_resp.status_code == 401


def test_get_artifact_not_found_404(test_client, make_authenticated_headers) -> None:
    resp = test_client.get("/api/v1/artifacts/999999", headers=make_authenticated_headers())
    assert resp.status_code == 404


def test_list_evidence_artifacts_exposes_source_derived_chain(
    test_db, test_client, tmp_path: Path, make_authenticated_headers
) -> None:
    """Phase 24 task scope, "Evidence Details": the full source/derived
    provenance chain must be listable via one endpoint, with
    `parent_artifact_id` letting the frontend render it as a chain."""
    evidence = _make_evidence(test_db, "CASE-ART-4")
    master_path = tmp_path / "master.mp4"
    master_path.write_bytes(b"master bytes")
    master = Artifact(
        evidence_id=evidence.id,
        artifact_type="cp_plus_hevc_master_mp4",
        path=str(master_path),
        size_bytes=master_path.stat().st_size,
        sha256="master-hash",
    )
    test_db.add(master)
    test_db.commit()
    test_db.refresh(master)

    preview_path = tmp_path / "preview.mp4"
    preview_path.write_bytes(b"preview bytes")
    preview = Artifact(
        evidence_id=evidence.id,
        parent_artifact_id=master.id,
        artifact_type="cp_plus_h264_preview_mp4",
        path=str(preview_path),
        size_bytes=preview_path.stat().st_size,
        sha256="preview-hash",
    )
    test_db.add(preview)
    test_db.commit()
    test_db.refresh(preview)

    resp = test_client.get(
        f"/api/v1/evidence/{evidence.id}/artifacts", headers=make_authenticated_headers()
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["id"] == master.id
    assert body[0]["parent_artifact_id"] is None
    assert body[1]["id"] == preview.id
    assert body[1]["parent_artifact_id"] == master.id


def test_list_evidence_artifacts_unknown_evidence_404(
    test_client, make_authenticated_headers
) -> None:
    # Case-access resolution (Phase 25) now 404s a nonexistent evidence
    # item before the route body runs, unlike the empty `200 []` this
    # used to return -- consistent with every other evidence-scoped route.
    resp = test_client.get(
        "/api/v1/evidence/999999/artifacts", headers=make_authenticated_headers()
    )
    assert resp.status_code == 404


def test_download_artifact_missing_file_on_disk_404(
    test_db, test_client, tmp_path: Path, make_authenticated_headers
) -> None:
    evidence = _make_evidence(test_db, "CASE-ART-3")
    missing_path = tmp_path / "gone.mp4"
    artifact = Artifact(
        evidence_id=evidence.id, artifact_type="cp_plus_h264_preview_mp4", path=str(missing_path)
    )
    test_db.add(artifact)
    test_db.commit()
    test_db.refresh(artifact)

    resp = test_client.get(
        f"/api/v1/artifacts/{artifact.id}/download", headers=make_authenticated_headers()
    )
    assert resp.status_code == 404
