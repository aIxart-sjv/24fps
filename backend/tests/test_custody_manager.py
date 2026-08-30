"""DB-level tests for app/core/custody_manager.py (Phase 21, Part A).

Mirrors tests/test_audit_chain_manager.py's style: exercise the manager
directly against a real (in-memory) database, then verify tamper
detection by mutating persisted rows and re-running Phase 16's existing
verifier -- never a second verifier.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.audit.hash_chain import ChainFailureReason
from app.core.audit_chain_manager import AuditChainManager
from app.core.auth_manager import AuthManager
from app.core.case_manager import CaseManager
from app.core.custody_manager import CustodyManager
from app.core.evidence_manager import EvidenceManager
from app.models import CustodyTransferStatus, CustodyTransferType, ProcessingEvent, UserRole
from app.schemas.case import CaseCreateRequest
from app.schemas.evidence import EvidenceCreateRequest


def _make_case_and_evidence(db, case_id: str = "CASE-CUSTODY-1"):
    case = CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Custody test"))
    evidence = EvidenceManager.register_evidence(
        db,
        case_id=case.id,
        request=EvidenceCreateRequest(
            evidence_id=f"{case_id}-EV-1", source_type="disk_image", source_description="disk"
        ),
    )
    return case, evidence


def _make_user(db, username: str, role: UserRole = UserRole.OFFICER):
    return AuthManager.create_user(
        db, username=username, display_name=username.title(), password="password123", role=role
    )


class TestInitialIntake:
    def test_record_initial_custody_creates_accepted_intake(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        officer = _make_user(test_db, "officer_intake")
        transfer = CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer
        )
        assert transfer.transfer_type == CustodyTransferType.INTAKE
        assert transfer.status == CustodyTransferStatus.ACCEPTED
        assert transfer.releasing_user_id is None
        assert transfer.receiving_user_id == officer.id
        assert transfer.provenance_event_id is not None

    def test_duplicate_intake_rejected(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        officer = _make_user(test_db, "officer_dup")
        CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer
        )
        with pytest.raises(ValueError, match="already has recorded custody"):
            CustodyManager.record_initial_custody(
                test_db, evidence_id=evidence.id, receiving_user=officer
            )

    def test_intake_for_missing_evidence_rejected(self, test_db) -> None:
        officer = _make_user(test_db, "officer_missing_ev")
        with pytest.raises(ValueError, match="not found"):
            CustodyManager.record_initial_custody(
                test_db, evidence_id=999999, receiving_user=officer
            )

    def test_current_custodian_none_before_intake(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        assert CustodyManager.get_current_custodian(test_db, evidence.id) is None

    def test_current_custodian_after_intake(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        officer = _make_user(test_db, "officer_cc")
        CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer
        )
        custodian = CustodyManager.get_current_custodian(test_db, evidence.id)
        assert custodian is not None
        assert custodian.id == officer.id


class TestInitiateHandoff:
    def test_current_custodian_can_initiate(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        officer_a = _make_user(test_db, "officer_a")
        officer_b = _make_user(test_db, "officer_b")
        CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer_a
        )
        issued = CustodyManager.initiate_handoff(
            test_db, evidence_id=evidence.id, initiator=officer_a, receiving_user=officer_b
        )
        assert issued.transfer.status == CustodyTransferStatus.PENDING
        assert issued.transfer.transfer_type == CustodyTransferType.TRANSFER
        assert len(issued.raw_token) > 20
        assert issued.transfer.token_hash is not None
        assert issued.transfer.token_hash != issued.raw_token

    def test_non_custodian_cannot_initiate(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        officer_a = _make_user(test_db, "officer_a2")
        officer_b = _make_user(test_db, "officer_b2")
        officer_c = _make_user(test_db, "officer_c2")
        CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer_a
        )
        with pytest.raises(PermissionError):
            CustodyManager.initiate_handoff(
                test_db, evidence_id=evidence.id, initiator=officer_b, receiving_user=officer_c
            )

    def test_cannot_initiate_without_prior_intake(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        officer_a = _make_user(test_db, "officer_a3")
        officer_b = _make_user(test_db, "officer_b3")
        with pytest.raises(ValueError, match="no recorded custodian"):
            CustodyManager.initiate_handoff(
                test_db, evidence_id=evidence.id, initiator=officer_a, receiving_user=officer_b
            )

    def test_cannot_initiate_to_self(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        officer_a = _make_user(test_db, "officer_a4")
        CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer_a
        )
        with pytest.raises(ValueError, match="oneself"):
            CustodyManager.initiate_handoff(
                test_db, evidence_id=evidence.id, initiator=officer_a, receiving_user=officer_a
            )

    def test_cannot_initiate_to_inactive_user(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        officer_a = _make_user(test_db, "officer_a5")
        officer_b = _make_user(test_db, "officer_b5")
        officer_b.is_active = False
        test_db.commit()
        CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer_a
        )
        with pytest.raises(ValueError, match="not active"):
            CustodyManager.initiate_handoff(
                test_db, evidence_id=evidence.id, initiator=officer_a, receiving_user=officer_b
            )

    def test_duplicate_pending_transfer_rejected(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db)
        officer_a = _make_user(test_db, "officer_a6")
        officer_b = _make_user(test_db, "officer_b6")
        officer_c = _make_user(test_db, "officer_c6")
        CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer_a
        )
        CustodyManager.initiate_handoff(
            test_db, evidence_id=evidence.id, initiator=officer_a, receiving_user=officer_b
        )
        with pytest.raises(ValueError, match="already has a pending"):
            CustodyManager.initiate_handoff(
                test_db, evidence_id=evidence.id, initiator=officer_a, receiving_user=officer_c
            )


class TestAcceptRejectCancel:
    def _setup_pending(self, test_db, prefix: str):
        case, evidence = _make_case_and_evidence(test_db, case_id=f"CASE-{prefix}")
        officer_a = _make_user(test_db, f"{prefix}_a")
        officer_b = _make_user(test_db, f"{prefix}_b")
        CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer_a
        )
        issued = CustodyManager.initiate_handoff(
            test_db, evidence_id=evidence.id, initiator=officer_a, receiving_user=officer_b
        )
        return case, evidence, officer_a, officer_b, issued

    def test_correct_receiver_can_accept(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "acc1")
        transfer = CustodyManager.accept_handoff(
            test_db, raw_token=issued.raw_token, accepting_user=officer_b
        )
        assert transfer.status == CustodyTransferStatus.ACCEPTED
        assert transfer.accepted_at is not None
        assert transfer.provenance_event_id is not None
        custodian = CustodyManager.get_current_custodian(test_db, evidence.id)
        assert custodian is not None
        assert custodian.id == officer_b.id

    def test_wrong_receiver_rejected_and_state_unchanged(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "acc2")
        wrong_user = _make_user(test_db, "acc2_wrong")
        with pytest.raises(PermissionError):
            CustodyManager.accept_handoff(
                test_db, raw_token=issued.raw_token, accepting_user=wrong_user
            )
        # State never changed by the rejected attempt.
        transfer = CustodyManager.get_pending_transfer(test_db, evidence.id)
        assert transfer is not None
        assert transfer.status == CustodyTransferStatus.PENDING

    def test_replayed_token_after_accept_fails(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "acc3")
        CustodyManager.accept_handoff(test_db, raw_token=issued.raw_token, accepting_user=officer_b)
        with pytest.raises(ValueError, match="no longer pending"):
            CustodyManager.accept_handoff(
                test_db, raw_token=issued.raw_token, accepting_user=officer_b
            )

    def test_malformed_token_rejected(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "acc4")
        with pytest.raises(ValueError, match="No custody transfer matches"):
            CustodyManager.accept_handoff(
                test_db, raw_token="totally-bogus-token", accepting_user=officer_b
            )

    def test_empty_token_rejected(self, test_db) -> None:
        officer = _make_user(test_db, "acc5_officer")
        with pytest.raises(ValueError, match="Malformed"):
            CustodyManager.accept_handoff(test_db, raw_token="", accepting_user=officer)

    def test_expired_token_rejected(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "acc6")
        issued.transfer.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        test_db.commit()
        with pytest.raises(ValueError, match="no longer pending"):
            CustodyManager.accept_handoff(
                test_db, raw_token=issued.raw_token, accepting_user=officer_b
            )
        refreshed = CustodyManager.get_transfer(test_db, issued.transfer.id)
        assert refreshed is not None
        assert refreshed.status == CustodyTransferStatus.EXPIRED

    def test_reject_by_intended_receiver_leaves_custodian_unchanged(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "rej1")
        transfer = CustodyManager.reject_handoff(
            test_db, raw_token=issued.raw_token, rejecting_user=officer_b
        )
        assert transfer.status == CustodyTransferStatus.REJECTED
        assert transfer.provenance_event_id is None
        custodian = CustodyManager.get_current_custodian(test_db, evidence.id)
        assert custodian is not None
        assert custodian.id == officer_a.id

    def test_reject_by_wrong_user_forbidden(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "rej2")
        wrong_user = _make_user(test_db, "rej2_wrong")
        with pytest.raises(PermissionError):
            CustodyManager.reject_handoff(
                test_db, raw_token=issued.raw_token, rejecting_user=wrong_user
            )

    def test_cancel_by_initiator_succeeds(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "can1")
        transfer = CustodyManager.cancel_handoff(
            test_db, transfer_id=issued.transfer.id, cancelling_user=officer_a
        )
        assert transfer.status == CustodyTransferStatus.CANCELLED
        custodian = CustodyManager.get_current_custodian(test_db, evidence.id)
        assert custodian is not None
        assert custodian.id == officer_a.id

    def test_cancel_by_non_initiator_forbidden(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "can2")
        with pytest.raises(PermissionError):
            CustodyManager.cancel_handoff(
                test_db, transfer_id=issued.transfer.id, cancelling_user=officer_b
            )

    def test_cancel_already_accepted_fails(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "can3")
        CustodyManager.accept_handoff(test_db, raw_token=issued.raw_token, accepting_user=officer_b)
        with pytest.raises(ValueError, match="no longer pending"):
            CustodyManager.cancel_handoff(
                test_db, transfer_id=issued.transfer.id, cancelling_user=officer_a
            )

    def test_after_cancel_new_handoff_may_be_initiated(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = self._setup_pending(test_db, "can4")
        CustodyManager.cancel_handoff(
            test_db, transfer_id=issued.transfer.id, cancelling_user=officer_a
        )
        officer_c = _make_user(test_db, "can4_c")
        new_issued = CustodyManager.initiate_handoff(
            test_db, evidence_id=evidence.id, initiator=officer_a, receiving_user=officer_c
        )
        assert new_issued.transfer.status == CustodyTransferStatus.PENDING


class TestLabAcceptance:
    def test_lab_personnel_accept_uses_same_mechanism(self, test_db) -> None:
        case, evidence = _make_case_and_evidence(test_db, case_id="CASE-LAB")
        officer = _make_user(test_db, "lab_officer")
        lab_tech = _make_user(test_db, "lab_tech", role=UserRole.LAB_PERSONNEL)
        CustodyManager.record_initial_custody(
            test_db, evidence_id=evidence.id, receiving_user=officer
        )
        issued = CustodyManager.initiate_handoff(
            test_db, evidence_id=evidence.id, initiator=officer, receiving_user=lab_tech
        )
        transfer = CustodyManager.accept_handoff(
            test_db, raw_token=issued.raw_token, accepting_user=lab_tech
        )
        assert transfer.status == CustodyTransferStatus.ACCEPTED
        custodian = CustodyManager.get_current_custodian(test_db, evidence.id)
        assert custodian is not None
        assert custodian.id == lab_tech.id
        assert custodian.role == UserRole.LAB_PERSONNEL


class TestCustodyHistoryAndAuditIntegration:
    def test_history_is_chronological_and_read_only(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = TestAcceptRejectCancel()._setup_pending(
            test_db, "hist1"
        )
        CustodyManager.accept_handoff(test_db, raw_token=issued.raw_token, accepting_user=officer_b)
        history = CustodyManager.get_custody_history(test_db, evidence.id)
        assert len(history) == 2
        assert history[0].transfer_type == CustodyTransferType.INTAKE
        assert history[1].transfer_type == CustodyTransferType.TRANSFER
        assert [t.id for t in history] == sorted(t.id for t in history)

    def test_completed_transfers_recorded_as_processing_events(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = TestAcceptRejectCancel()._setup_pending(
            test_db, "hist2"
        )
        CustodyManager.accept_handoff(test_db, raw_token=issued.raw_token, accepting_user=officer_b)
        events = (
            test_db.query(ProcessingEvent)
            .filter(ProcessingEvent.case_id == case.id)
            .order_by(ProcessingEvent.id)
            .all()
        )
        assert len(events) == 2
        for event in events:
            assert event.operation == "physical_custody_transfer"
            assert event.actor_type == "human"

    def test_pending_transfer_is_never_recorded_as_processing_event(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = TestAcceptRejectCancel()._setup_pending(
            test_db, "hist3"
        )
        events = test_db.query(ProcessingEvent).filter(ProcessingEvent.case_id == case.id).all()
        # Only the intake event exists -- the still-PENDING transfer has none.
        assert len(events) == 1

    def test_audit_chain_valid_after_full_lifecycle(self, test_db) -> None:
        case, evidence, officer_a, officer_b, issued = TestAcceptRejectCancel()._setup_pending(
            test_db, "hist4"
        )
        CustodyManager.accept_handoff(test_db, raw_token=issued.raw_token, accepting_user=officer_b)
        result = AuditChainManager.verify_case_chain(test_db, case.id)
        assert result.valid is True
        assert result.event_count == 2

    def test_tampering_a_custody_event_is_detected_by_existing_verifier(self, test_db) -> None:
        """Task Phase 21 scope: audit tampering of a custody event must
        be detected by Phase 16's existing verifier -- no second
        verifier is built for this test."""
        case, evidence, officer_a, officer_b, issued = TestAcceptRejectCancel()._setup_pending(
            test_db, "hist5"
        )
        CustodyManager.accept_handoff(test_db, raw_token=issued.raw_token, accepting_user=officer_b)
        tampered = (
            test_db.query(ProcessingEvent)
            .filter(ProcessingEvent.case_id == case.id)
            .order_by(ProcessingEvent.id)
            .first()
        )
        assert tampered is not None
        tampered.description = "tampered description, not what actually happened"
        test_db.commit()

        result = AuditChainManager.verify_case_chain(test_db, case.id)
        assert result.valid is False
        assert result.failure is not None
        assert result.failure.reason == ChainFailureReason.CURRENT_HASH_MISMATCH
