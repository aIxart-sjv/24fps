"""
API routes for evidence integrity hashing and verification.
Master Specification Section 46 (API Design), Section 38 (Integrity Engine).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.integrity.hash_verification import IntegrityManager
from app.schemas.hash import HashResponse
from app.storage.db import get_db

router = APIRouter()


@router.post(
    "/evidence/{evidence_id}/hash",
    response_model=list[HashResponse],
    status_code=status.HTTP_201_CREATED,
)
def hash_evidence(evidence_id: int, db: Session = Depends(get_db)) -> list[HashResponse]:
    """Compute and store the initial SHA-256 and MD5 hashes for evidence."""
    try:
        hashes = IntegrityManager.hash_evidence(db, evidence_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [HashResponse.model_validate(hash_row) for hash_row in hashes]


@router.post("/evidence/{evidence_id}/verify", response_model=list[HashResponse])
def verify_evidence(evidence_id: int, db: Session = Depends(get_db)) -> list[HashResponse]:
    """Recompute evidence hashes and compare them against stored values."""
    try:
        hashes = IntegrityManager.verify_evidence(db, evidence_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [HashResponse.model_validate(hash_row) for hash_row in hashes]


@router.get("/evidence/{evidence_id}/hashes", response_model=list[HashResponse])
def list_evidence_hashes(evidence_id: int, db: Session = Depends(get_db)) -> list[HashResponse]:
    """List all stored hashes for an evidence item."""
    try:
        hashes = IntegrityManager.list_evidence_hashes(db, evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [HashResponse.model_validate(hash_row) for hash_row in hashes]
