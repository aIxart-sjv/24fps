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

from app.adapters.factory import build_default_registry
from app.api.deps import require_case_access_for_evidence
from app.core.evidence_manager import EvidenceManager
from app.models import Device, Evidence
from app.schemas.device import (
    DeviceIdentificationResult,
    DeviceResponse,
    VendorSupportSummaryResponse,
)
from app.storage.db import get_db

router = APIRouter()


@router.get("/devices/support-matrix", response_model=list[VendorSupportSummaryResponse])
def get_support_matrix() -> list[VendorSupportSummaryResponse]:
    """Report every registered vendor adapter's real, declared support
    level and capabilities (Phase 19's support matrix).

    Phase 23 gap assessment: no route exposed `AdapterRegistry.
    support_matrix()` before this -- the frontend "Devices / OEM Support"
    view had nothing to read to avoid falsely claiming every vendor is
    fully supported. `build_default_registry()` (Phase 19's own test/
    composition helper) is reused as-is; this route builds one registry
    per request (registries are cheap, in-memory, stateless value
    objects -- see that factory's own docstring) rather than introducing
    a process-wide singleton for a low-traffic read endpoint.

    Not case-scoped (no evidence/case is involved -- this is static,
    global vendor-capability metadata), so it carries no case-access
    dependency.
    """
    registry = build_default_registry()
    return [
        VendorSupportSummaryResponse(
            vendor=summary.vendor,
            model_pattern=summary.model_pattern,
            firmware_pattern=summary.firmware_pattern,
            model_scope=summary.model_scope,
            support_level=summary.support_level.value,
            support_level_label=summary.support_level.name,
            evidence_basis=[b.value for b in summary.evidence_basis],
            capabilities=[c.value for c in summary.capabilities],
            limitations=list(summary.limitations),
            adapter_version=summary.adapter_version,
        )
        for summary in registry.support_matrix()
    ]


@router.post("/evidence/{evidence_id}/identify-device", response_model=DeviceIdentificationResult)
def identify_device(
    evidence_id: int,
    db: Session = Depends(get_db),
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> DeviceIdentificationResult:
    """Run Phase 6 device identification and persist the result onto `Device`.

    Safe to call repeatedly — re-running identification updates the
    existing `Device` row rather than rejecting a duplicate.
    """
    del evidence
    try:
        _device, result = EvidenceManager.identify_device(db, evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result


@router.get("/evidence/{evidence_id}/device", response_model=DeviceResponse)
def get_device(
    evidence_id: int,
    db: Session = Depends(get_db),
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> DeviceResponse:
    """Retrieve previously persisted device identification for an evidence item."""
    del evidence
    device = db.query(Device).filter(Device.evidence_id == evidence_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No device identification recorded for evidence {evidence_id}",
        )
    return DeviceResponse.model_validate(device)


@router.post("/evidence/{evidence_id}/detect-format", response_model=DeviceIdentificationResult)
def detect_format(
    evidence_id: int,
    db: Session = Depends(get_db),
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> DeviceIdentificationResult:
    """Run Phase 6 storage/format identification and persist the result onto `Storage`.

    Safe to call repeatedly, matching `identify_device`.
    """
    del evidence
    try:
        _storage, result = EvidenceManager.detect_format(db, evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result
