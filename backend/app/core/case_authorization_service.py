"""
Central case-level authorization service (Phase 25, "Case-Level Access
Control / Admin Permission Matrix").

This is the ONE place case-access decisions are made -- every protected
route depends on it (directly, or via the `app.api.deps.require_case_access*`
FastAPI dependencies built on top of it) rather than re-implementing an
"is this user allowed to see this case" check independently in each of the
~20 route files that touch case-scoped data (task section 4: "Do NOT
duplicate authorization checks independently in 20 routes").

============================================================================
ROLE POLICY (task section 3/15 -- documented here, the one place it is
enforced)
============================================================================
- `UserRole.ADMIN`: unconditional access to every case. Never represented
  as a `CaseUserAccess` row (task: "cannot be accidentally restricted by a
  normal case assignment") -- `can_view_case` special-cases the role
  directly, before ever querying `CaseUserAccess`.
- `UserRole.OFFICER`: access only to cases with an `ACTIVE`
  `CaseUserAccess` row for that (user, case) pair. Cannot grant/revoke
  access (enforced by `grant_case_access`/`revoke_case_access` requiring
  an admin caller, and by the admin-only routes that call them).
- `UserRole.LAB_PERSONNEL`: identical policy to `OFFICER`. The codebase
  gap assessment (`app.models.user`'s own docstring, and a repo-wide
  search) found no existing lab-specific workflow or automatic-access
  concept for this role to plug into -- task section 3 explicitly requires
  "do not automatically receive access to every case merely because they
  are authenticated", so the conservative, spec-compliant default is the
  same explicit-grant model as `OFFICER`, not a silent bypass.

These are the only two axes: `UserRole` (fixed per account) and case
access (dynamic, per (user, case) pair) are never conflated (task section
15) -- there is no "clearance level" here, decorative or otherwise.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.audit import ActorType
from app.audit.events import ProcessingOperation
from app.core.provenance_manager import ProvenanceManager
from app.models import (
    AIResult,
    Artifact,
    Case,
    CaseUserAccess,
    CaseAccessStatus,
    CustodyTransfer,
    Evidence,
    Finding,
    Job,
    JobStatus,
    Recording,
    Report,
    User,
    UserRole,
)

__all__ = [
    "CaseAccessDeniedError",
    "CaseAuthorizationService",
]


class CaseAccessDeniedError(Exception):
    """Raised when an authenticated user is not authorized to view/act on
    a case. Distinct from `ValueError` (used throughout this codebase for
    "not found") so callers -- `app.api.deps`'s dependencies -- can map it
    to `403 Forbidden` rather than `404 Not Found` (task section 25: an
    officer probing a case ID they cannot access must get a real 403, not
    a 404 that would at least confirm the ID exists -- callers may choose
    to fold this into a 404 anyway where hiding existence is preferred,
    but the distinct exception type keeps that a deliberate choice, not an
    accident of reusing `ValueError` for both)."""


class CaseAuthorizationService:
    """Service layer for case-level access grants and authorization checks."""

    # ---- Core authorization checks ---------------------------------------

    @staticmethod
    def can_view_case(db: Session, user: User, case_id: int) -> bool:
        """Whether `user` may currently view/access case `case_id`.

        `ADMIN` is unconditional. Everyone else needs an `ACTIVE`
        `CaseUserAccess` row for exactly this (user, case) pair -- never
        inferred from role, evidence ownership, or any other signal.
        """
        if user.role == UserRole.ADMIN:
            return True
        grant = (
            db.query(CaseUserAccess)
            .filter(
                CaseUserAccess.user_id == user.id,
                CaseUserAccess.case_id == case_id,
                CaseUserAccess.status == CaseAccessStatus.ACTIVE,
            )
            .first()
        )
        return grant is not None

    @staticmethod
    def require_case_access(db: Session, user: User, case_id: int) -> Case:
        """`can_view_case`, but raises instead of returning a bool --
        the shape every protected route actually wants.

        Raises:
            ValueError: `case_id` does not exist (-> 404).
            CaseAccessDeniedError: the case exists but `user` may not
                view it (-> 403).
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if case is None:
            raise ValueError(f"Case with id {case_id} not found")
        if not CaseAuthorizationService.can_view_case(db, user, case_id):
            raise CaseAccessDeniedError(
                f"user {user.id} ({user.username!r}) does not have access to case {case_id}"
            )
        return case

    # ---- Grant / revoke (admin-only -- enforced by the caller) ----------

    @staticmethod
    def _upsert_active_grant(
        db: Session, *, user_id: int, case_id: int, granted_by_user_id: int, reason: str | None
    ) -> CaseUserAccess:
        """Shared upsert body for `grant_case_access` and
        `grant_initial_access_to_creator` -- the only difference between
        them is *who is allowed to call this at all* and whose identity
        `ProvenanceManager` records as the actor, both handled by the
        caller. Idempotent: granting an already-active pair just
        refreshes `granted_at`/`granted_by`/`reason` (task section 20's
        multi-officer grant/revoke sequencing implies repeatable calls
        should be safe, matching every other manager's established
        idempotency convention in this codebase) -- never raises
        "already granted" as an error.
        """
        grant = (
            db.query(CaseUserAccess)
            .filter(CaseUserAccess.user_id == user_id, CaseUserAccess.case_id == case_id)
            .first()
        )
        now = datetime.now(UTC)
        if grant is None:
            grant = CaseUserAccess(
                case_id=case_id,
                user_id=user_id,
                status=CaseAccessStatus.ACTIVE,
                granted_by_user_id=granted_by_user_id,
                granted_at=now,
                reason=reason,
            )
            db.add(grant)
        else:
            grant.status = CaseAccessStatus.ACTIVE
            grant.granted_by_user_id = granted_by_user_id
            grant.granted_at = now
            grant.revoked_at = None
            grant.revoked_by_user_id = None
            grant.reason = reason
        db.commit()
        db.refresh(grant)
        return grant

    @staticmethod
    def grant_case_access(
        db: Session,
        admin: User,
        *,
        user_id: int,
        case_id: int,
        reason: str | None = None,
    ) -> CaseUserAccess:
        """Grant (or re-grant, if previously revoked) `user_id` access to
        `case_id`. Idempotent -- see `_upsert_active_grant`.

        Raises:
            ValueError: `admin` is not an `ADMIN`, or `case_id`/`user_id`
                does not exist.
        """
        if admin.role != UserRole.ADMIN:
            raise ValueError("only an administrator may grant case access")

        if db.query(Case).filter(Case.id == case_id).first() is None:
            raise ValueError(f"Case with id {case_id} not found")
        target_user = db.query(User).filter(User.id == user_id).first()
        if target_user is None:
            raise ValueError(f"User with id {user_id} not found")

        grant = CaseAuthorizationService._upsert_active_grant(
            db, user_id=user_id, case_id=case_id, granted_by_user_id=admin.id, reason=reason
        )

        ProvenanceManager.record_event(
            db,
            case_id=case_id,
            operation=ProcessingOperation.CASE_ACCESS_CHANGE.value,
            actor=admin.display_name,
            actor_type=ActorType.HUMAN,
            status=JobStatus.COMPLETED,
            description=f"Granted case access to {target_user.display_name} ({target_user.username})",
            parameters={
                "action": "grant",
                "target_user_id": user_id,
                "target_username": target_user.username,
            },
            notes=reason,
        )
        return grant

    @staticmethod
    def grant_initial_access_to_creator(db: Session, case: Case, creator: User) -> CaseUserAccess:
        """Automatic access grant for a case's own creator (task section
        13: "creator automatically receives access... do not accidentally
        create an inaccessible case").

        Deliberately NOT `grant_case_access` with `creator` passed as the
        acting admin -- that method requires an `ADMIN` caller by design,
        and an `OFFICER`/`LAB_PERSONNEL` creator is exactly the case this
        exists for. This is the platform bootstrapping the creator's own
        access as a direct consequence of case creation, not one user
        granting another access -- so `granted_by_user_id` is the
        creator's own id, and the audit event's actor is the creator
        (`ActorType.HUMAN`: they did, genuinely, just create this case).

        Callers only need this for a non-`ADMIN` creator (an `ADMIN`'s
        access is already unconditional) -- `app/api/routes/cases.py`'s
        `create_case` only calls it in that branch.
        """
        grant = CaseAuthorizationService._upsert_active_grant(
            db,
            user_id=creator.id,
            case_id=case.id,
            granted_by_user_id=creator.id,
            reason="automatic grant to case creator",
        )
        ProvenanceManager.record_event(
            db,
            case_id=case.id,
            operation=ProcessingOperation.CASE_ACCESS_CHANGE.value,
            actor=creator.display_name,
            actor_type=ActorType.HUMAN,
            status=JobStatus.COMPLETED,
            description=f"{creator.display_name} ({creator.username}) created this case and "
            "automatically received access to it",
            parameters={
                "action": "grant",
                "target_user_id": creator.id,
                "target_username": creator.username,
            },
        )
        return grant

    @staticmethod
    def revoke_case_access(
        db: Session,
        admin: User,
        *,
        user_id: int,
        case_id: int,
        reason: str | None = None,
    ) -> CaseUserAccess:
        """Revoke `user_id`'s access to `case_id`. Idempotent: revoking an
        already-revoked (or never-granted-but-existing-row) pair is a
        no-op status-wise but still records the attempt's audit event
        only when a real state transition happens, so the audit trail
        never claims a revoke that did not change anything.

        Raises:
            ValueError: `admin` is not an `ADMIN`, `case_id`/`user_id`
                does not exist, or there is no grant at all for this pair
                (nothing to revoke).
        """
        if admin.role != UserRole.ADMIN:
            raise ValueError("only an administrator may revoke case access")

        case = db.query(Case).filter(Case.id == case_id).first()
        if case is None:
            raise ValueError(f"Case with id {case_id} not found")
        target_user = db.query(User).filter(User.id == user_id).first()
        if target_user is None:
            raise ValueError(f"User with id {user_id} not found")

        grant = (
            db.query(CaseUserAccess)
            .filter(CaseUserAccess.user_id == user_id, CaseUserAccess.case_id == case_id)
            .first()
        )
        if grant is None:
            raise ValueError(
                f"user {user_id} has no access grant recorded for case {case_id} to revoke"
            )

        was_active = grant.status == CaseAccessStatus.ACTIVE
        grant.status = CaseAccessStatus.REVOKED
        grant.revoked_at = datetime.now(UTC)
        grant.revoked_by_user_id = admin.id
        if reason is not None:
            grant.reason = reason
        db.commit()
        db.refresh(grant)

        if was_active:
            ProvenanceManager.record_event(
                db,
                case_id=case_id,
                operation=ProcessingOperation.CASE_ACCESS_CHANGE.value,
                actor=admin.display_name,
                actor_type=ActorType.HUMAN,
                status=JobStatus.COMPLETED,
                description=(
                    f"Revoked case access from {target_user.display_name} ({target_user.username})"
                ),
                parameters={
                    "action": "revoke",
                    "target_user_id": user_id,
                    "target_username": target_user.username,
                },
                notes=reason,
            )
        return grant

    # ---- Reads ------------------------------------------------------------

    @staticmethod
    def list_case_access(db: Session, case_id: int) -> list[CaseUserAccess]:
        """Every access grant (active or revoked) ever recorded for one
        case, most recently granted first."""
        return (
            db.query(CaseUserAccess)
            .filter(CaseUserAccess.case_id == case_id)
            .order_by(CaseUserAccess.granted_at.desc())
            .all()
        )

    @staticmethod
    def list_user_cases(db: Session, user: User) -> list[Case]:
        """The cases `user` may currently view -- every case for an
        `ADMIN`, otherwise exactly the cases with an `ACTIVE` grant. This
        is what backs case listing (task section 6: "Officer case list:
        return ONLY cases the officer is authorized to access... Do not
        fetch all cases to the frontend and hide unauthorized rows using
        CSS")."""
        if user.role == UserRole.ADMIN:
            return db.query(Case).order_by(Case.id).all()
        return (
            db.query(Case)
            .join(CaseUserAccess, CaseUserAccess.case_id == Case.id)
            .filter(
                CaseUserAccess.user_id == user.id,
                CaseUserAccess.status == CaseAccessStatus.ACTIVE,
            )
            .order_by(Case.id)
            .all()
        )

    @staticmethod
    def get_access_matrix(
        db: Session,
    ) -> tuple[list[Case], list[User], dict[tuple[int, int], bool]]:
        """The full case x user access grid in a small, fixed number of
        queries (task section 23: "Do not perform one database query per
        matrix cell"): one query for every case, one for every user, one
        for every ACTIVE grant -- never N+1.

        Returns:
            `(cases, users, active_by_case_and_user)` where the third
            element maps `(case_id, user_id) -> True` for exactly the
            pairs with an active grant (absence means no access; `ADMIN`
            users are not looked up here at all -- callers render their
            row as unconditionally `True` for every case instead, per
            `can_view_case`'s own admin special-case).
        """
        cases = db.query(Case).order_by(Case.id).all()
        users = db.query(User).order_by(User.id).all()
        active_grants = (
            db.query(CaseUserAccess).filter(CaseUserAccess.status == CaseAccessStatus.ACTIVE).all()
        )
        active_by_pair = {(g.case_id, g.user_id): True for g in active_grants}
        return cases, users, active_by_pair

    # ---- Resource -> case_id resolvers (used by app.api.deps) -----------

    @staticmethod
    def resolve_case_id_for_evidence(db: Session, evidence_id: int) -> int | None:
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        return evidence.case_id if evidence is not None else None

    @staticmethod
    def resolve_case_id_for_recording(db: Session, recording_id: int) -> int | None:
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if recording is None:
            return None
        return CaseAuthorizationService.resolve_case_id_for_evidence(db, recording.evidence_id)

    @staticmethod
    def resolve_case_id_for_artifact(db: Session, artifact_id: int) -> int | None:
        artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if artifact is None:
            return None
        return CaseAuthorizationService.resolve_case_id_for_evidence(db, artifact.evidence_id)

    @staticmethod
    def resolve_case_id_for_job(db: Session, job_id: int) -> int | None:
        job = db.query(Job).filter(Job.id == job_id).first()
        return job.case_id if job is not None else None

    @staticmethod
    def resolve_case_id_for_finding(db: Session, finding_id: int) -> int | None:
        finding = db.query(Finding).filter(Finding.id == finding_id).first()
        return finding.case_id if finding is not None else None

    @staticmethod
    def resolve_case_id_for_report(db: Session, report_id: int) -> int | None:
        report = db.query(Report).filter(Report.id == report_id).first()
        return report.case_id if report is not None else None

    @staticmethod
    def resolve_case_id_for_transfer(db: Session, transfer_id: int) -> int | None:
        transfer = db.query(CustodyTransfer).filter(CustodyTransfer.id == transfer_id).first()
        if transfer is None:
            return None
        return CaseAuthorizationService.resolve_case_id_for_evidence(db, transfer.evidence_id)

    @staticmethod
    def resolve_case_id_for_ai_result(db: Session, ai_result_id: int) -> int | None:
        result = db.query(AIResult).filter(AIResult.id == ai_result_id).first()
        return result.case_id if result is not None else None
