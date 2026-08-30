"""
API routes for Phase 6 device/format identification.
Master Specification Section 46 (API Design): "IDENTIFICATION" (
identify-device, GET device) and the `detect-format` route from the
"FILESYSTEM" section — `parse` from that same section is Phase 7+ and is
not implemented here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.evidence_manager import EvidenceManager
from app.models import Device
from app.schemas.device import DeviceIdentificationResult, DeviceResponse
from app.storage.db import get_db

router = APIRouter()


@router.post("/evidence/{evidence_id}/identify-device", response_model=DeviceIdentificationResult)
def identify_device(evidence_id: int, db: Session = Depends(get_db)) -> DeviceIdentificationResult:
    """Run Phase 6 device identification and persist the result onto `Device`.

    Safe to call repeatedly — re-running identification updates the
    existing `Device` row rather than rejecting a duplicate.
    """
    try:
        _device, result = EvidenceManager.identify_device(db, evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result


@router.get("/evidence/{evidence_id}/device", response_model=DeviceResponse)
def get_device(evidence_id: int, db: Session = Depends(get_db)) -> DeviceResponse:
    """Retrieve previously persisted device identification for an evidence item."""
    device = db.query(Device).filter(Device.evidence_id == evidence_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No device identification recorded for evidence {evidence_id}",
        )
    return DeviceResponse.model_validate(device)


@router.post("/evidence/{evidence_id}/detect-format", response_model=DeviceIdentificationResult)
def detect_format(evidence_id: int, db: Session = Depends(get_db)) -> DeviceIdentificationResult:
    """Run Phase 6 storage/format identification and persist the result onto `Storage`.

    Safe to call repeatedly, matching `identify_device`.
    """
    try:
        _storage, result = EvidenceManager.detect_format(db, evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result
