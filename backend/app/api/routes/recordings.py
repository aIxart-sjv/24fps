"""
API routes for recording discovery, session linking, and extraction
(Phase 9, "Recording Extraction + FFmpeg").
Master Specification Section 46 (API Design), `RECORDINGS` section, plus
two added routes — the doc explicitly allows this ("Exact routes can
evolve"): `link-session` composes the multi-segment session-linking
capability `app.core.recording_manager.RecordingManager.link_session` adds
on top of Phase 8's per-file parsing; `refresh-media-metadata` (Phase
24.1) re-probes already-produced derived media to backfill technical
metadata without re-extracting.

Every route is case-access-protected (Phase 25) via
`app.api.deps.require_case_access_for_evidence`/
`require_case_access_for_recording` -- a recording is exactly the kind of
case-scoped resource task section 5 names explicitly ("recordings").
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_case_access_for_evidence, require_case_access_for_recording
from app.core.recording_manager import RecordingManager
from app.models import Evidence, Recording, RecordingMetadata
from app.schemas.metadata import RecordingMetadataResponse
from app.schemas.recording import RecordingResponse, RecordingSessionLinkRequest
from app.storage.db import get_db

router = APIRouter()


@router.get("/evidence/{evidence_id}/recordings", response_model=list[RecordingResponse])
def enumerate_recordings(
    evidence_id: int,
    db: Session = Depends(get_db),
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> list[RecordingResponse]:
    """Discover and persist recordings found on one evidence item.

    Safe to call repeatedly — re-running discovery updates the existing
    `Recording` row rather than duplicating it. Returns an empty list
    (not an error) when the evidence does not match a supported vendor
    structure.
    """
    del evidence
    try:
        recordings = RecordingManager.enumerate_recordings(db, evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [RecordingResponse.model_validate(r) for r in recordings]


@router.post(
    "/evidence/{evidence_id}/recordings/link-session",
    response_model=RecordingResponse,
    status_code=status.HTTP_201_CREATED,
)
def link_session(
    evidence_id: int,
    request: RecordingSessionLinkRequest,
    db: Session = Depends(get_db),
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> RecordingResponse:
    """Link an ordered sequence of CP Plus segments into one session `Recording`.

    `evidence_id` (the anchor/first segment) is validated to be the first
    entry of `request.evidence_ids`; the full ordered list is what is
    actually linked. `RecordingManager.link_session` itself rejects
    segments spanning more than one case, so authorizing on the anchor's
    case is sufficient -- it is the only case any segment here can belong
    to by the time the manager call succeeds.
    """
    del evidence
    if not request.evidence_ids or request.evidence_ids[0] != evidence_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request.evidence_ids must start with the path's evidence_id (the session's "
            "anchor/first segment)",
        )
    try:
        recording = RecordingManager.link_session(db, request.evidence_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RecordingResponse.model_validate(recording)


@router.get("/recordings/{recording_id}", response_model=RecordingResponse)
def get_recording(
    recording: Recording = Depends(require_case_access_for_recording),
) -> RecordingResponse:
    """Retrieve a previously discovered/linked recording by primary key."""
    return RecordingResponse.model_validate(recording)


@router.post("/recordings/{recording_id}/extract", response_model=RecordingResponse)
def extract_recording(
    recording_id: int,
    db: Session = Depends(get_db),
    recording: Recording = Depends(require_case_access_for_recording),
) -> RecordingResponse:
    """Reconstruct, mux (FFmpeg), and register the playable output for one recording.

    Never fails the HTTP request for a partial/failed extraction outcome —
    that is reported via `GET /recordings/{recording_id}/metadata`'s
    `extraction_status`/`extraction_warnings` entries instead.
    """
    del recording
    try:
        updated = RecordingManager.extract_recording(db, recording_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RecordingResponse.model_validate(updated)


@router.post("/recordings/{recording_id}/refresh-media-metadata", response_model=RecordingResponse)
def refresh_recording_media_metadata(
    recording_id: int,
    db: Session = Depends(get_db),
    recording: Recording = Depends(require_case_access_for_recording),
) -> RecordingResponse:
    """Re-probe this recording's already-produced derived media (never
    re-extracting/re-muxing/re-transcoding) and persist the actual
    codec/container/width/height/fps/duration.

    Backfills `Recording` rows whose technical metadata was never
    captured -- e.g. rows written before `POST .../extract` tracked this
    metadata, or a recording whose HEVC master mux failed but whose H.264
    preview still exists. 400s only for programmer/caller-error-class
    problems (no recording, or no derived media artifact to probe yet);
    a probe that itself comes back unavailable is reported via
    `GET /recordings/{recording_id}/metadata`'s
    `media_metadata_refresh_status`/`_warnings` entries instead.
    """
    del recording
    try:
        updated = RecordingManager.refresh_media_metadata(db, recording_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RecordingResponse.model_validate(updated)


@router.get("/recordings/{recording_id}/metadata", response_model=list[RecordingMetadataResponse])
def get_recording_metadata(
    recording_id: int,
    db: Session = Depends(get_db),
    recording: Recording = Depends(require_case_access_for_recording),
) -> list[RecordingMetadataResponse]:
    """List every metadata entry recorded against a recording.

    Surfaces the diagnostic detail extraction produces (source segment
    list, session-link status, extraction status/warnings, timestamp
    provenance, derived-artifact ids) — Master Specification Section 50's
    `metadata` table.
    """
    del recording
    entries = (
        db.query(RecordingMetadata).filter(RecordingMetadata.recording_id == recording_id).all()
    )
    return [RecordingMetadataResponse.model_validate(e) for e in entries]
