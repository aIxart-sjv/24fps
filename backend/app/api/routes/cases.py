"""
API routes for case and evidence management.
Master Specification Section 46 (API Design).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.schemas.case import CaseCreateRequest, CaseResponse, CaseUpdateRequest
from app.schemas.evidence import EvidenceCreateRequest, EvidenceResponse
from app.storage.db import get_db

router = APIRouter()


@router.post("/cases", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(request: CaseCreateRequest, db: Session = Depends(get_db)) -> CaseResponse:
    """Create a new forensic case."""
    try:
        case = CaseManager.create_case(db, request)
        return CaseResponse.model_validate(case)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/cases", response_model=list[CaseResponse])
def list_cases(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[CaseResponse]:
    """List all forensic cases with pagination."""
    cases = CaseManager.list_cases(db, skip=skip, limit=limit)
    return [CaseResponse.model_validate(case) for case in cases]


@router.get("/cases/{case_id}", response_model=CaseResponse)
def get_case(case_id: int, db: Session = Depends(get_db)) -> CaseResponse:
    """Retrieve a specific case by ID."""
    case = CaseManager.get_case(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with id {case_id} not found",
        )
    return CaseResponse.model_validate(case)


@router.patch("/cases/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: int,
    request: CaseUpdateRequest,
    db: Session = Depends(get_db),
) -> CaseResponse:
    """Update an existing case."""
    case = CaseManager.update_case(db, case_id, request)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with id {case_id} not found",
        )
    return CaseResponse.model_validate(case)


@router.post(
    "/cases/{case_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_evidence(
    case_id: int,
    request: EvidenceCreateRequest,
    db: Session = Depends(get_db),
) -> EvidenceResponse:
    """Register new evidence in a case."""
    try:
        evidence = EvidenceManager.register_evidence(db, case_id, request)
        return EvidenceResponse.model_validate(evidence)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceResponse])
def list_case_evidence(
    case_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[EvidenceResponse]:
    """List all evidence items in a case."""
    case = CaseManager.get_case(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with id {case_id} not found",
        )
    evidence_list = EvidenceManager.list_case_evidence(db, case_id, skip=skip, limit=limit)
    return [EvidenceResponse.model_validate(ev) for ev in evidence_list]


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(evidence_id: int, db: Session = Depends(get_db)) -> EvidenceResponse:
    """Retrieve evidence by ID."""
    evidence = EvidenceManager.get_evidence(db, evidence_id)
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with id {evidence_id} not found",
        )
    return EvidenceResponse.model_validate(evidence)
