"""Tests for app/reporting/evidence_report.py (Phase 18) -- DB-level,
verifying `assemble_report_data` reads existing case state correctly
without recomputing or reinterpreting it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.audit_chain_manager import AuditChainManager
from app.core.case_manager import CaseManager
from app.reporting.evidence_report import REPORT_SCHEMA_VERSION, assemble_report_data
from app.reporting.json_report import render_json
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base
from tests.fixtures.report_case import build_rich_case


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---- Complete case ---------------------------------------------------


def test_complete_case_populates_every_section(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")

    assert data.metadata.report_schema_version == REPORT_SCHEMA_VERSION
    assert data.metadata.case_id == rich.case.id
    assert data.case.evidence_count == 1
    assert len(data.evidence) == 1
    assert len(data.acquisition) == 1
    assert data.acquisition[0].storage_present is True
    assert len(data.identification) == 1
    assert data.identification[0].device_present is True
    assert len(data.recordings) == 1
    assert len(data.recovery) == 1
    assert len(data.timeline) == 3  # 2 source events + 1 correlated event
    assert len(data.correlation) == 1
    assert len(data.ai.detections) == 1
    assert len(data.ai.tracks) == 1
    assert len(data.ai.motion_events) == 1
    assert len(data.validation) == 1
    assert len(data.provenance) == 3  # parsing, validation, blockchain_anchor
    assert data.audit.valid is True
    assert len(data.blockchain) == 1
    assert data.limitations  # unresolved timestamp / preview / unvalidated recovery / local-test


def test_source_references_are_traceable(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")

    assert data.evidence[0].evidence_id == rich.evidence.id
    assert data.recordings[0].recording_id == rich.recording.id
    assert data.recordings[0].master_artifact_id == rich.master_artifact.id
    assert data.recordings[0].preview_artifact_id == rich.preview_artifact.id
    assert data.recovery[0].recovery_result_id == rich.recovery.id
    assert data.correlation[0].correlated_event_id == rich.correlated_event_id
    assert data.blockchain[0].chain_id == f"case-{rich.case.id}"


def test_cp_plus_master_vs_preview_distinction_preserved(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")

    entry = data.recordings[0]
    assert entry.master_artifact_type == "cp_plus_hevc_master_mp4"
    assert entry.preview_artifact_type == "cp_plus_h264_preview_mp4"
    assert entry.master_artifact_id != entry.preview_artifact_id
    # Never described as the same recording artifact.
    assert entry.master_artifact_path != entry.preview_artifact_path


# ---- Minimal case ------------------------------------------------------


def test_minimal_case_has_empty_sections_and_no_crash(db) -> None:
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-MIN-1", name="Minimal"))
    data = assemble_report_data(db, case, software_version="0.1.0")

    assert data.case.evidence_count == 0
    assert data.evidence == []
    assert data.acquisition == []
    assert data.identification == []
    assert data.recordings == []
    assert data.recovery == []
    assert data.timeline == []
    assert data.correlation == []
    assert data.ai.detections == []
    assert data.ai.tracks == []
    assert data.ai.motion_events == []
    assert data.validation == []
    assert data.provenance == []
    assert data.audit.valid is True
    assert data.audit.event_count == 0
    assert data.blockchain == []
    # No limitations were derivable from an empty case except the
    # always-applicable "no blockchain anchor" note.
    assert any(lim.category == "blockchain" for lim in data.limitations)


# ---- Unresolved timestamps / partial recovery / invalid chain -----------


def test_unresolved_cp_plus_timestamp_is_flagged_not_verified(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")

    entry = data.recordings[0]
    assert entry.metadata_entries.get("timestamp_status") == "raw_counter_unvalidated"
    assert any(lim.category == "timestamp" for lim in data.limitations)
    # Never silently upgraded to "verified".
    combined = " ".join(lim.description for lim in data.limitations)
    assert "verified" not in combined.lower() or "not been independently verified" in combined


def test_partial_recovery_is_never_labeled_validated(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")

    entry = data.recovery[0]
    assert entry.status == "partial"
    assert entry.validation_state == "unvalidated_framework"
    assert entry.validation_state != "validated"


def test_invalid_audit_chain_is_reported_invalid_never_valid(db) -> None:
    rich = build_rich_case(db)
    from app.models import ProcessingEvent

    first_event = (
        db.query(ProcessingEvent)
        .filter(ProcessingEvent.case_id == rich.case.id)
        .order_by(ProcessingEvent.id.asc())
        .first()
    )
    first_event.status = "failed"
    db.commit()

    # Confirm the underlying chain really is broken (sanity check).
    assert AuditChainManager.verify_case_chain(db, rich.case.id).valid is False

    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    assert data.audit.valid is False
    assert data.audit.failure_event_id is not None
    assert data.audit.failure_reason is not None
    assert any(lim.category == "audit" for lim in data.limitations)


def test_local_test_blockchain_anchor_is_labeled_not_real_network(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")

    anchor = data.blockchain[0]
    assert anchor.provider == "local_testnet"
    assert anchor.is_real_network is False
    assert any(
        lim.category == "blockchain" and "LOCAL/TEST" in lim.description for lim in data.limitations
    )


def test_case_with_no_anchor_flags_missing_blockchain_anchor(db) -> None:
    case = CaseManager.create_case(db, CaseCreateRequest(case_id="CASE-NOANCHOR", name="No anchor"))
    data = assemble_report_data(db, case, software_version="0.1.0")
    assert data.blockchain == []
    assert any(
        lim.category == "blockchain" and "No blockchain anchor" in lim.description
        for lim in data.limitations
    )


# ---- Deterministic serialization -----------------------------------------


def test_repeated_assembly_of_unchanged_state_is_byte_identical(db) -> None:
    rich = build_rich_case(db)
    data1 = assemble_report_data(db, rich.case, software_version="0.1.0")
    data2 = assemble_report_data(db, rich.case, software_version="0.1.0")

    # `generated_at`/`checked_at` legitimately differ (wall-clock) --
    # confirm everything else is identical by comparing with those
    # fields normalized out.
    import dataclasses

    normalized1 = dataclasses.replace(
        data1,
        metadata=dataclasses.replace(data1.metadata, generated_at="X"),
        audit=dataclasses.replace(data1.audit, checked_at="X"),
    )
    normalized2 = dataclasses.replace(
        data2,
        metadata=dataclasses.replace(data2.metadata, generated_at="X"),
        audit=dataclasses.replace(data2.audit, checked_at="X"),
    )
    assert normalized1 == normalized2
    assert render_json(normalized1) == render_json(normalized2)


def test_validation_evidence_kind_classification(db) -> None:
    rich = build_rich_case(db)
    data = assemble_report_data(db, rich.case, software_version="0.1.0")
    assert data.validation[0].dataset_id == "DS-REAL-CPPLUS"
    assert data.validation[0].evidence_kind == "real_evidence"
