"""Unit tests for app/core/case_authorization_service.py (Phase 25,
"Case-Level Access Control / Admin Permission Matrix") -- the service
layer directly, independent of HTTP. See test_case_authorization_api.py
for the HTTP-level/IDOR/route-coverage tests task sections 16-20 ask for.
"""

from __future__ import annotations

import pytest

from app.core.auth_manager import AuthManager
from app.core.case_authorization_service import CaseAccessDeniedError, CaseAuthorizationService
from app.core.case_manager import CaseManager
from app.models import CaseAccessStatus, CaseUserAccess, UserRole
from app.schemas.case import CaseCreateRequest


def _make_case(db, case_id: str):
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name=case_id))


def _make_user(db, username: str, role: UserRole = UserRole.OFFICER):
    return AuthManager.create_user(
        db, username=username, display_name=username.title(), password="password123", role=role
    )


# ---- can_view_case / require_case_access -----------------------------------


def test_admin_can_view_any_case_without_a_grant_row(test_db) -> None:
    admin = _make_user(test_db, "svc_admin_1", role=UserRole.ADMIN)
    case = _make_case(test_db, "SVC-ADMIN-1")
    assert CaseAuthorizationService.can_view_case(test_db, admin, case.id) is True
    # No CaseUserAccess row was ever created for the admin.
    assert (
        test_db.query(CaseUserAccess)
        .filter(CaseUserAccess.user_id == admin.id, CaseUserAccess.case_id == case.id)
        .first()
        is None
    )


def test_officer_cannot_view_unassigned_case(test_db) -> None:
    officer = _make_user(test_db, "svc_officer_1")
    case = _make_case(test_db, "SVC-OFF-1")
    assert CaseAuthorizationService.can_view_case(test_db, officer, case.id) is False


def test_officer_can_view_case_after_grant(test_db) -> None:
    admin = _make_user(test_db, "svc_admin_2", role=UserRole.ADMIN)
    officer = _make_user(test_db, "svc_officer_2")
    case = _make_case(test_db, "SVC-OFF-2")
    CaseAuthorizationService.grant_case_access(test_db, admin, user_id=officer.id, case_id=case.id)
    assert CaseAuthorizationService.can_view_case(test_db, officer, case.id) is True


def test_lab_personnel_follows_the_same_explicit_grant_policy_as_officer(test_db) -> None:
    admin = _make_user(test_db, "svc_admin_lab", role=UserRole.ADMIN)
    lab = _make_user(test_db, "svc_lab_1", role=UserRole.LAB_PERSONNEL)
    case = _make_case(test_db, "SVC-LAB-1")

    # No automatic access merely from being authenticated.
    assert CaseAuthorizationService.can_view_case(test_db, lab, case.id) is False

    CaseAuthorizationService.grant_case_access(test_db, admin, user_id=lab.id, case_id=case.id)
    assert CaseAuthorizationService.can_view_case(test_db, lab, case.id) is True


def test_require_case_access_raises_value_error_for_missing_case(test_db) -> None:
    officer = _make_user(test_db, "svc_officer_404")
    with pytest.raises(ValueError, match="not found"):
        CaseAuthorizationService.require_case_access(test_db, officer, 999999)


def test_require_case_access_raises_access_denied_for_unassigned_officer(test_db) -> None:
    officer = _make_user(test_db, "svc_officer_denied")
    case = _make_case(test_db, "SVC-DENIED-1")
    with pytest.raises(CaseAccessDeniedError):
        CaseAuthorizationService.require_case_access(test_db, officer, case.id)


# ---- grant / revoke ----------------------------------------------------


def test_grant_case_access_requires_admin_caller(test_db) -> None:
    officer = _make_user(test_db, "svc_not_admin")
    target = _make_user(test_db, "svc_target_1")
    case = _make_case(test_db, "SVC-GRANT-NOTADMIN")
    with pytest.raises(ValueError, match="administrator"):
        CaseAuthorizationService.grant_case_access(
            test_db, officer, user_id=target.id, case_id=case.id
        )


def test_grant_case_access_is_idempotent(test_db) -> None:
    admin = _make_user(test_db, "svc_admin_idem", role=UserRole.ADMIN)
    officer = _make_user(test_db, "svc_officer_idem")
    case = _make_case(test_db, "SVC-IDEM-1")

    first = CaseAuthorizationService.grant_case_access(
        test_db, admin, user_id=officer.id, case_id=case.id
    )
    second = CaseAuthorizationService.grant_case_access(
        test_db, admin, user_id=officer.id, case_id=case.id
    )
    assert first.id == second.id  # same row, not a duplicate
    rows = (
        test_db.query(CaseUserAccess)
        .filter(CaseUserAccess.user_id == officer.id, CaseUserAccess.case_id == case.id)
        .all()
    )
    assert len(rows) == 1


def test_revoke_then_regrant_reuses_the_same_row(test_db) -> None:
    admin = _make_user(test_db, "svc_admin_regrant", role=UserRole.ADMIN)
    officer = _make_user(test_db, "svc_officer_regrant")
    case = _make_case(test_db, "SVC-REGRANT-1")

    granted = CaseAuthorizationService.grant_case_access(
        test_db, admin, user_id=officer.id, case_id=case.id
    )
    CaseAuthorizationService.revoke_case_access(test_db, admin, user_id=officer.id, case_id=case.id)
    assert CaseAuthorizationService.can_view_case(test_db, officer, case.id) is False

    regranted = CaseAuthorizationService.grant_case_access(
        test_db, admin, user_id=officer.id, case_id=case.id
    )
    assert regranted.id == granted.id
    assert regranted.status == CaseAccessStatus.ACTIVE
    assert regranted.revoked_at is None
    assert CaseAuthorizationService.can_view_case(test_db, officer, case.id) is True


def test_revoke_case_access_requires_admin_caller(test_db) -> None:
    admin = _make_user(test_db, "svc_admin_for_revoke_check", role=UserRole.ADMIN)
    officer = _make_user(test_db, "svc_officer_for_revoke_check")
    other_officer = _make_user(test_db, "svc_officer_attempting_revoke")
    case = _make_case(test_db, "SVC-REVOKE-NOTADMIN")
    CaseAuthorizationService.grant_case_access(test_db, admin, user_id=officer.id, case_id=case.id)
    with pytest.raises(ValueError, match="administrator"):
        CaseAuthorizationService.revoke_case_access(
            test_db, other_officer, user_id=officer.id, case_id=case.id
        )
    # Access must remain untouched by the rejected attempt.
    assert CaseAuthorizationService.can_view_case(test_db, officer, case.id) is True


def test_revoking_one_officer_never_affects_another(test_db) -> None:
    """Task section 20: multiple officers on one case, revoking one must
    never touch the other's access."""
    admin = _make_user(test_db, "svc_admin_multi", role=UserRole.ADMIN)
    officer_1 = _make_user(test_db, "svc_multi_1")
    officer_2 = _make_user(test_db, "svc_multi_2")
    case = _make_case(test_db, "SVC-MULTI-1")

    CaseAuthorizationService.grant_case_access(
        test_db, admin, user_id=officer_1.id, case_id=case.id
    )
    CaseAuthorizationService.grant_case_access(
        test_db, admin, user_id=officer_2.id, case_id=case.id
    )
    assert CaseAuthorizationService.can_view_case(test_db, officer_1, case.id) is True
    assert CaseAuthorizationService.can_view_case(test_db, officer_2, case.id) is True

    CaseAuthorizationService.revoke_case_access(
        test_db, admin, user_id=officer_1.id, case_id=case.id
    )
    assert CaseAuthorizationService.can_view_case(test_db, officer_1, case.id) is False
    assert CaseAuthorizationService.can_view_case(test_db, officer_2, case.id) is True


def test_admin_is_never_restricted_by_a_normal_case_assignment(test_db) -> None:
    """Task section 3: admin access cannot be accidentally restricted."""
    admin = _make_user(test_db, "svc_admin_never_restricted", role=UserRole.ADMIN)
    case = _make_case(test_db, "SVC-ADMIN-UNRESTRICTED")
    # Admin never appears as a CaseUserAccess row, granted or otherwise --
    # access remains unconditional regardless.
    assert CaseAuthorizationService.can_view_case(test_db, admin, case.id) is True
    assert test_db.query(CaseUserAccess).filter(CaseUserAccess.user_id == admin.id).first() is None


# ---- list_user_cases / get_access_matrix -------------------------------


def test_list_user_cases_admin_sees_everything(test_db) -> None:
    admin = _make_user(test_db, "svc_admin_list", role=UserRole.ADMIN)
    _make_case(test_db, "SVC-LIST-A")
    _make_case(test_db, "SVC-LIST-B")
    cases = CaseAuthorizationService.list_user_cases(test_db, admin)
    ids = {c.case_id for c in cases}
    assert {"SVC-LIST-A", "SVC-LIST-B"}.issubset(ids)


def test_list_user_cases_officer_sees_only_assigned(test_db) -> None:
    admin = _make_user(test_db, "svc_admin_list2", role=UserRole.ADMIN)
    officer = _make_user(test_db, "svc_officer_list2")
    case_a = _make_case(test_db, "SVC-LIST2-A")
    _make_case(test_db, "SVC-LIST2-B")  # never granted

    CaseAuthorizationService.grant_case_access(
        test_db, admin, user_id=officer.id, case_id=case_a.id
    )
    cases = CaseAuthorizationService.list_user_cases(test_db, officer)
    assert [c.case_id for c in cases] == ["SVC-LIST2-A"]


def test_get_access_matrix_reflects_active_grants_only(test_db) -> None:
    admin = _make_user(test_db, "svc_admin_matrix", role=UserRole.ADMIN)
    officer = _make_user(test_db, "svc_officer_matrix")
    case = _make_case(test_db, "SVC-MATRIX-1")

    CaseAuthorizationService.grant_case_access(test_db, admin, user_id=officer.id, case_id=case.id)
    cases, users, active = CaseAuthorizationService.get_access_matrix(test_db)
    assert (case.id, officer.id) in active
    assert (case.id, admin.id) not in active  # admins are never grant rows

    CaseAuthorizationService.revoke_case_access(test_db, admin, user_id=officer.id, case_id=case.id)
    _cases2, _users2, active_after_revoke = CaseAuthorizationService.get_access_matrix(test_db)
    assert (case.id, officer.id) not in active_after_revoke


# ---- resolvers ----------------------------------------------------------


def test_resolve_case_id_for_evidence(test_db) -> None:
    from app.core.evidence_manager import EvidenceManager
    from app.schemas.evidence import EvidenceCreateRequest

    case = _make_case(test_db, "SVC-RESOLVE-EV")
    evidence = EvidenceManager.register_evidence(
        test_db,
        case.id,
        EvidenceCreateRequest(evidence_id="SVC-RESOLVE-EV-1", source_type="forensic_image"),
    )
    assert CaseAuthorizationService.resolve_case_id_for_evidence(test_db, evidence.id) == case.id
    assert CaseAuthorizationService.resolve_case_id_for_evidence(test_db, 999999) is None
