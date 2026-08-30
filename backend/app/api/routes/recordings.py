"""
API routes for recording discovery, session linking, and extraction
(Phase 9, "Recording Extraction + FFmpeg").
Master Specification Section 46 (API Design), `RECORDINGS` section, plus
one added route — the doc explicitly allows this ("Exact routes can
evolve"): `link-session` composes the multi-segment session-linking
capability `app.core.recording_manager.RecordingManager.link_session` adds
on top of Phase 8's per-file parsing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.recording_manager import RecordingManager
from app.models import Recording, RecordingMetadata
from app.schemas.metadata import RecordingMetadataResponse
from app.schemas.recording import RecordingResponse, RecordingSessionLinkRequest
from app.storage.db import get_db

router = APIRouter()


@router.get("/evidence/{evidence_id}/recordings", response_model=list[RecordingResponse])
def enumerate_recordings(evidence_id: int, db: Session = Depends(get_db)) -> list[RecordingResponse]:
    """Discover and persist recordings found on one evidence item.

    Safe to call repeatedly — re-running discovery updates the existing
    `Recording` row rather than duplicating it. Returns an empty list
    (not an error) when the evidence does not match a supported vendor
    structure.
    """
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
    evidence_id: int, request: RecordingSessionLinkRequest, db: Session = Depends(get_db)
) -> RecordingResponse:
    """Link an ordered sequence of CP Plus segments into one session `Recording`.

    `evidence_id` (the anchor/first segment) is validated to be the first
    entry of `request.evidence_ids`; the full ordered list is what is
    actually linked.
    """
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
def get_recording(recording_id: int, db: Session = Depends(get_db)) -> RecordingResponse:
    """Retrieve a previously discovered/linked recording by primary key."""
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recording found with id {recording_id}",
        )
    return RecordingResponse.model_validate(recording)


@router.post("/recordings/{recording_id}/extract", response_model=RecordingResponse)
def extract_recording(recording_id: int, db: Session = Depends(get_db)) -> RecordingResponse:
    """Reconstruct, mux (FFmpeg), and register the playable output for one recording.

    Never fails the HTTP request for a partial/failed extraction outcome —
    that is reported via `GET /recordings/{recording_id}/metadata`'s
    `extraction_status`/`extraction_warnings` entries instead.
    """
    try:
        recording = RecordingManager.extract_recording(db, recording_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RecordingResponse.model_validate(recording)


@router.get(
    "/recordings/{recording_id}/metadata", response_model=list[RecordingMetadataResponse]
)
def get_recording_metadata(
    recording_id: int, db: Session = Depends(get_db)
) -> list[RecordingMetadataResponse]:
    """List every metadata entry recorded against a recording.

    Surfaces the diagnostic detail extraction produces (source segment
    list, session-link status, extraction status/warnings, timestamp
    provenance, derived-artifact ids) — Master Specification Section 50's
    `metadata` table.
    """
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recording found with id {recording_id}",
        )
    entries = (
        db.query(RecordingMetadata).filter(RecordingMetadata.recording_id == recording_id).all()
    )
    return [RecordingMetadataResponse.model_validate(e) for e in entries]
