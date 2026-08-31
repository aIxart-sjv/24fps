"""
Shared FastAPI dependencies for authenticated/authorized routes (Phase 21,
Part A; Phase 25, "Case-Level Access Control / Admin Permission Matrix").

`get_current_user` is the single place an HTTP route resolves "who is
calling" -- every custody-mutating route depends on it rather than
trusting any caller-supplied identity field (task Phase 21 scope: "Custody
must never trust a caller-supplied arbitrary string... as proof of
identity"). It reads a bearer token from the `Authorization` header and
resolves it via `app.core.auth_manager.AuthManager.validate_session`,
which is the only code path that checks token hash/expiry/revocation.

`require_admin` and the `require_case_access*` family (Phase 25) are the
second layer: *authorization*, not identity. Every one of them is a thin
FastAPI-dependency wrapper around `app.core.case_authorization_service.
CaseAuthorizationService` -- the actual decision logic lives there exactly
once; these wrappers only (1) resolve the right path-param-named resource
by ID (mirroring each route's own existing 404 message, so adding one of
these dependencies to a route never changes its "not found" behavior) and
(2) translate `ValueError`/`CaseAccessDeniedError` into 404/403. Different
routes name their path parameter differently (`case_id`, `evidence_id`,
`recording_id`, ...), so FastAPI's automatic path-param-to-dependency-
parameter matching needs one small dependency per resource-identifier
shape rather than a single generic one (task section 4: "Do NOT duplicate
authorization checks independently in 20 routes" -- the checks themselves
are not duplicated, only this thin resolve-by-id plumbing is, once per
identifier shape rather than once per route).
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth_manager import AuthManager
from app.core.case_authorization_service import CaseAccessDeniedError, CaseAuthorizationService
from app.models import (
    Artifact,
    Case,
    CustodyTransfer,
    Evidence,
    Finding,
    Job,
    Recording,
    Report,
    User,
    UserRole,
)
from app.storage.db import get_db

__all__ = [
    "extract_bearer_token",
    "get_current_user",
    "get_current_user_from_header_or_query",
    "require_admin",
    "require_case_access",
    "require_case_access_for_artifact",
    "require_case_access_for_artifact_download",
    "require_case_access_for_evidence",
    "require_case_access_for_finding",
    "require_case_access_for_job",
    "require_case_access_for_recording",
    "require_case_access_for_report",
    "require_case_access_for_transfer",
]


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    return token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated caller from the `Authorization: Bearer
    <token>` header.

    Raises:
        HTTPException: 401 if the header is missing/malformed, or the
            token is unknown, expired, revoked, or belongs to a
            deactivated user.
    """
    token = extract_bearer_token(authorization)
    user = AuthManager.validate_session(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return user


def get_current_user_from_header_or_query(
    authorization: str | None = Header(default=None),
    token: str | None = None,
    db: Session = Depends(get_db),
) -> User:
    """Identical to `get_current_user`, plus a `?token=<raw session
    token>` query-string fallback used *only* when no `Authorization`
    header is present.

    Exists for exactly one reason: `GET /artifacts/{artifact_id}/download`
    is now case-access-protected (Phase 25), but it is loaded directly as
    a `<video src=...>` by the frontend's video workspace so the browser
    can stream it with native HTTP Range requests -- and a `<video>`
    element has no way to attach a custom `Authorization` header. Making
    that route open again to close that gap would defeat the entire point
    of Phase 25 (task section 5 names artifact/recording download data
    explicitly); routing video playback through an authenticated
    fetch-to-Blob instead would lose native Range-based seeking on large
    derived recordings. This is the deliberate, narrow trade-off instead:
    the *same* short-lived session token the caller already holds, passed
    as a query parameter on this one read-only streaming route -- never a
    new, separately-issued credential, and never used to widen what the
    token can do.

    Known limitation (documented, not silently accepted): a token passed
    this way can end up in server access logs or browser history for this
    URL. It is still bound to the same short TTL and revocation as every
    other use of that token (`AuthManager.validate_session`) -- it is not
    long-lived, and logging it out invalidates it exactly as it would for
    the header form.
    """
    if authorization:
        return get_current_user(authorization=authorization, db=db)
    resolved = AuthManager.validate_session(db, token or "")
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return resolved


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Gate a route to `UserRole.ADMIN` only (task section 7: "Admin-only
    operations must require ADMIN role"), matching the existing
    `POST /users` convention (`app/api/routes/users.py`) exactly."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this operation requires an administrator account",
        )
    return current_user


def _authorize_or_raise(db: Session, current_user: User, case_id: int) -> Case:
    """Shared `ValueError`/`CaseAccessDeniedError` -> 404/403 translation
    every `require_case_access*` dependency below funnels through."""
    try:
        return CaseAuthorizationService.require_case_access(db, current_user, case_id)
    except CaseAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def require_case_access(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Case:
    """For routes whose path parameter IS the case's primary key
    (`.../cases/{case_id}/...`). 404 if the case does not exist, 403 if
    `current_user` may not view it (task section 18, IDOR: a caller who
    knows a valid case ID they are not assigned to must still be
    rejected)."""
    return _authorize_or_raise(db, current_user, case_id)


def require_case_access_for_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Evidence:
    """For routes keyed by `evidence_id` (`.../evidence/{evidence_id}/...`)
    -- resolves the owning case via `Evidence.case_id` and applies the
    exact same check `require_case_access` does, so evidence/recordings/
    artifacts/etc. can never be reached merely by knowing their own ID
    while lacking access to the case that owns them (task section 5: "Do
    not protect only GET /cases/{id} while leaving GET /cases/{id}/evidence
    unprotected")."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with id {evidence_id} not found",
        )
    _authorize_or_raise(db, current_user, evidence.case_id)
    return evidence


def require_case_access_for_recording(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Recording:
    """For routes keyed by `recording_id` -- resolves the owning case via
    `Recording.evidence.case_id`."""
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if recording is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recording found with id {recording_id}",
        )
    case_id = CaseAuthorizationService.resolve_case_id_for_evidence(db, recording.evidence_id)
    assert case_id is not None  # Recording.evidence_id is a NOT NULL FK
    _authorize_or_raise(db, current_user, case_id)
    return recording


def require_case_access_for_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Artifact:
    """For routes keyed by `artifact_id` -- resolves the owning case via
    `Artifact.evidence.case_id`. Covers artifact *download* too (task
    section 5's own example of a route that must not be left
    unprotected): a downloaded derived recording is exactly the kind of
    case data an unassigned officer must not be able to fetch by ID."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact with id {artifact_id} not found",
        )
    case_id = CaseAuthorizationService.resolve_case_id_for_evidence(db, artifact.evidence_id)
    assert case_id is not None  # Artifact.evidence_id is a NOT NULL FK
    _authorize_or_raise(db, current_user, case_id)
    return artifact


def require_case_access_for_artifact_download(
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_header_or_query),
) -> Artifact:
    """Identical to `require_case_access_for_artifact`, but authenticates
    via `get_current_user_from_header_or_query` -- used only by
    `GET /artifacts/{artifact_id}/download` (see that dependency's own
    docstring for why this one route needs a query-token fallback)."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact with id {artifact_id} not found",
        )
    case_id = CaseAuthorizationService.resolve_case_id_for_evidence(db, artifact.evidence_id)
    assert case_id is not None  # Artifact.evidence_id is a NOT NULL FK
    _authorize_or_raise(db, current_user, case_id)
    return artifact


def require_case_access_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    """For routes keyed by `job_id` (or `root_job_id`, wired the same way
    -- see `app/api/routes/processing.py`'s own per-route wiring) --
    resolves the owning case via `Job.case_id` directly."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job with id {job_id} not found"
        )
    _authorize_or_raise(db, current_user, job.case_id)
    return job


def require_case_access_for_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Finding:
    """For routes keyed by `finding_id` -- resolves the owning case via
    `Finding.case_id` directly."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Finding with id {finding_id} not found"
        )
    _authorize_or_raise(db, current_user, finding.case_id)
    return finding


def require_case_access_for_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Report:
    """For routes keyed by `report_id` -- resolves the owning case via
    `Report.case_id` directly."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Report with id {report_id} not found"
        )
    _authorize_or_raise(db, current_user, report.case_id)
    return report


def require_case_access_for_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CustodyTransfer:
    """For the one custody route keyed by `transfer_id`
    (`POST /custody/handoff/{transfer_id}/cancel`) -- resolves the owning
    case via `CustodyTransfer.evidence.case_id`."""
    transfer = db.query(CustodyTransfer).filter(CustodyTransfer.id == transfer_id).first()
    if transfer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custody transfer with id {transfer_id} not found",
        )
    case_id = CaseAuthorizationService.resolve_case_id_for_evidence(db, transfer.evidence_id)
    assert case_id is not None  # CustodyTransfer.evidence_id is a NOT NULL FK
    _authorize_or_raise(db, current_user, case_id)
    return transfer
