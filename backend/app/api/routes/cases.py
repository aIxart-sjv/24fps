"""
API routes for case and evidence management.
Master Specification Section 46 (API Design).

Requires authentication on every route (Phase 24 task scope, "Authorization
Gap"): these routes predate Phase 21's `User`/session system and were never
retrofitted with `get_current_user`, unlike every route added from Phase 22
onward -- meaning an unauthenticated caller could list, read, and create
cases and evidence. This closed that specific gap.

Phase 25 closes the gap that Phase 24's own docstring here explicitly
flagged as remaining ("It does NOT add per-case access scoping... every
authenticated user can still see every case"): every route below that
reads or writes one specific case's data now depends on
`app.api.deps.require_case_access`/`require_case_access_for_evidence`,
backed by `app.core.case_authorization_service.CaseAuthorizationService`.
`GET /cases` (list) is handled differently -- see `list_cases` below --
since there is no single case ID to gate on; it filters server-side
instead (task section 6: "Do not fetch all cases to the frontend and hide
unauthorized rows using CSS").
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_case_access, require_case_access_for_evidence
from app.core.case_authorization_service import CaseAuthorizationService
from app.core.case_manager import CaseManager
from app.core.evidence_manager import EvidenceManager
from app.models import Case, Evidence, User, UserRole
from app.schemas.case import CaseCreateRequest, CaseResponse, CaseUpdateRequest
from app.schemas.evidence import EvidenceCreateRequest, EvidenceResponse
from app.storage.db import get_db

router = APIRouter()


@router.post("/cases", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    request: CaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseResponse:
    """Create a new forensic case.

    Task section 13: the creator automatically receives access, so a new
    case is never accidentally inaccessible. An `ADMIN` creator needs no
    explicit grant (their access is already unconditional); an `OFFICER`/
    `LAB_PERSONNEL` creator becomes an explicit `CaseUserAccess` member of
    their own new case, granted by themself.
    """
    try:
        case = CaseManager.create_case(db, request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if current_user.role != UserRole.ADMIN:
        CaseAuthorizationService.grant_initial_access_to_creator(db, case, current_user)
    return CaseResponse.model_validate(case)


@router.get("/cases", response_model=list[CaseResponse])
def list_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CaseResponse]:
    """List forensic cases.

    Task section 6: an `ADMIN` sees every case; anyone else sees only the
    cases they currently have `ACTIVE` access to -- filtered server-side
    (`CaseAuthorizationService.list_user_cases`), never returned in full
    for the frontend to selectively hide.
    """
    cases = CaseAuthorizationService.list_user_cases(db, current_user)
    return [CaseResponse.model_validate(case) for case in cases]


@router.get("/cases/{case_id}", response_model=CaseResponse)
def get_case(
    case: Case = Depends(require_case_access),
) -> CaseResponse:
    """Retrieve a specific case by ID."""
    return CaseResponse.model_validate(case)


@router.patch("/cases/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: int,
    request: CaseUpdateRequest,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> CaseResponse:
    """Update an existing case."""
    del case  # existence + access already established by the dependency
    updated = CaseManager.update_case(db, case_id, request)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with id {case_id} not found",
        )
    return CaseResponse.model_validate(updated)


@router.post(
    "/cases/{case_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_evidence(
    case_id: int,
    request: EvidenceCreateRequest,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> EvidenceResponse:
    """Register new evidence in a case."""
    del case
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
    case: Case = Depends(require_case_access),
) -> list[EvidenceResponse]:
    """List all evidence items in a case."""
    del case
    evidence_list = EvidenceManager.list_case_evidence(db, case_id, skip=skip, limit=limit)
    return [EvidenceResponse.model_validate(ev) for ev in evidence_list]


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(
    evidence: Evidence = Depends(require_case_access_for_evidence),
) -> EvidenceResponse:
    """Retrieve evidence by ID."""
    return EvidenceResponse.model_validate(evidence)
