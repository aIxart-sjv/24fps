"""
API routes for the admin case-access matrix (Phase 25, "Case-Level Access
Control / Admin Permission Matrix").

Every route here is admin-only (`app.api.deps.require_admin`). Business
logic lives entirely in `app.core.case_authorization_service.
CaseAuthorizationService` -- these routes only translate HTTP <-> service
calls, matching every other route module's established shape.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.case_authorization_service import CaseAuthorizationService
from app.models import CaseUserAccess, User
from app.schemas.case_access import (
    AccessMatrixCase,
    AccessMatrixResponse,
    AccessMatrixUserRow,
    CaseAccessGrantRequest,
    CaseAccessResponse,
)
from app.storage.db import get_db

router = APIRouter()


def _access_response(access: CaseUserAccess) -> CaseAccessResponse:
    return CaseAccessResponse(
        id=access.id,
        case_id=access.case_id,
        case_business_id=access.case.case_id,
        user_id=access.user_id,
        username=access.user.username,
        user_display_name=access.user.display_name,
        status=access.status.value,
        granted_by_user_id=access.granted_by_user_id,
        granted_by_display_name=access.granted_by.display_name,
        granted_at=access.granted_at,
        revoked_at=access.revoked_at,
        revoked_by_user_id=access.revoked_by_user_id,
        revoked_by_display_name=access.revoked_by.display_name if access.revoked_by else None,
        reason=access.reason,
    )


@router.get("/admin/case-access", response_model=AccessMatrixResponse)
def get_access_matrix(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> AccessMatrixResponse:
    """The full case x user access matrix (task section 7/21) -- every
    registered case as a column, every registered user as a row. Built
    from three queries total, never one per cell (task section 23)."""
    del current_user
    cases, users, active_by_pair = CaseAuthorizationService.get_access_matrix(db)
    return AccessMatrixResponse(
        cases=[AccessMatrixCase(id=c.id, case_id=c.case_id, name=c.name) for c in cases],
        users=[
            AccessMatrixUserRow(
                user_id=u.id,
                username=u.username,
                display_name=u.display_name,
                role=u.role.value,
                access_by_case_id={
                    # An ADMIN's row is unconditionally all-True (task
                    # section 3: admins are never represented as, or
                    # restricted by, an individual case grant); every
                    # other role reflects the real ACTIVE-grant state.
                    c.id: (u.role.value == "admin") or active_by_pair.get((c.id, u.id), False)
                    for c in cases
                },
            )
            for u in users
        ],
    )


@router.get("/admin/cases/{case_id}/access", response_model=list[CaseAccessResponse])
def list_case_access(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[CaseAccessResponse]:
    """Every access grant (active or revoked) ever recorded for one case."""
    del current_user
    return [_access_response(a) for a in CaseAuthorizationService.list_case_access(db, case_id)]


@router.post(
    "/admin/cases/{case_id}/access/{user_id}",
    response_model=CaseAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
def grant_case_access(
    case_id: int,
    user_id: int,
    body: CaseAccessGrantRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> CaseAccessResponse:
    """Grant one user access to one case.

    The acting administrator is always the authenticated caller
    (`current_user`, resolved from the session) -- never a caller-supplied
    field (task section 25: "the authenticated admin identity must come
    from the session").
    """
    try:
        access = CaseAuthorizationService.grant_case_access(
            db,
            current_user,
            user_id=user_id,
            case_id=case_id,
            reason=body.reason if body else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _access_response(access)


@router.delete(
    "/admin/cases/{case_id}/access/{user_id}",
    response_model=CaseAccessResponse,
)
def revoke_case_access(
    case_id: int,
    user_id: int,
    body: CaseAccessGrantRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> CaseAccessResponse:
    """Revoke one user's access to one case."""
    try:
        access = CaseAuthorizationService.revoke_case_access(
            db,
            current_user,
            user_id=user_id,
            case_id=case_id,
            reason=body.reason if body else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _access_response(access)
