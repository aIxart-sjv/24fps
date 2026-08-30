"""Tests for app/core/provenance_manager.py (Phase 15) -- DB-level, against
synthetic Case/Evidence/Artifact/Job rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit import ActorType, CustodyEventType, ProcessingOperation
from app.core.case_manager import CaseManager
from app.core.job_manager import JobManager
from app.core.provenance_manager import ProvenanceManager
from app.models import Artifact, Case, Evidence, JobStatus
from app.schemas.case import CaseCreateRequest
from app.storage.db import Base

_T0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)


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


def _make_case(db, case_id: str = "CASE-PROV-1") -> Case:
    return CaseManager.create_case(db, CaseCreateRequest(case_id=case_id, name="Provenance test"))


def _make_evidence(db, case: Case, *, evidence_id: str = "EVID-1") -> Evidence:
    evidence = Evidence(evidence_id=evidence_id, case_id=case.id, source_type="cp_plus")
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def _make_artifact(
    db, evidence: Evidence, *, artifact_type: str, path: str, parent: Artifact | None = None
) -> Artifact:
    artifact = Artifact(
        evidence_id=evidence.id,
        artifact_type=artifact_type,
        path=path,
        parent_artifact_id=parent.id if parent else None,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


# --- Basic lineage (task section 24) ------------------------------------


def test_basic_three_hop_lineage(db) -> None:
    case = _make_case(db)
    evidence = _make_evidence(db, case)
    artifact_a = _make_artifact(db, evidence, artifact_type="stream", path="/a")
    artifact_b = _make_artifact(db, evidence, artifact_type="master", path="/b", parent=artifact_a)
    artifact_c = _make_artifact(db, evidence, artifact_type="derived", path="/c", parent=artifact_b)

    # A traces to evidence.
    assert ProvenanceManager.get_artifact_source(db, artifact_a.id).id == evidence.id
    # B traces to A.
    ancestors_b = ProvenanceManager.get_artifact_ancestors(db, artifact_b.id)
    assert [a.id for a in ancestors_b] == [artifact_a.id]
    # C traces to B (and transitively to A).
    ancestors_c = ProvenanceManager.get_artifact_ancestors(db, artifact_c.id)
    assert [a.id for a in ancestors_c] == [artifact_a.id, artifact_b.id]
    # Reverse traversal reaches the original evidence.
    assert ProvenanceManager.get_artifact_source(db, artifact_c.id).id == evidence.id


def test_get_artifact_source_raises_for_missing_artifact(db) -> None:
    with pytest.raises(ValueError, match="not found"):
        ProvenanceManager.get_artifact_source(db, 999999)


# --- Multiple children (task section 25) --------------------------------


def test_multiple_children_of_one_artifact_are_both_discoverable(db) -> None:
    case = _make_case(db)
    evidence = _make_evidence(db, case)
    artifact_a = _make_artifact(db, evidence, artifact_type="stream", path="/a")
    artifact_b = _make_artifact(db, evidence, artifact_type="master", path="/b", parent=artifact_a)
    artifact_c = _make_artifact(db, evidence, artifact_type="preview", path="/c", parent=artifact_a)

    descendants = ProvenanceManager.get_artifact_descendants(db, artifact_a.id)

    assert {d.id for d in descendants} == {artifact_b.id, artifact_c.id}


def test_get_artifact_descendants_is_recursive(db) -> None:
    case = _make_case(db)
    evidence = _make_evidence(db, case)
    a = _make_artifact(db, evidence, artifact_type="stream", path="/a")
    b = _make_artifact(db, evidence, artifact_type="master", path="/b", parent=a)
    c = _make_artifact(db, evidence, artifact_type="grandchild", path="/c", parent=b)

    descendants = ProvenanceManager.get_artifact_descendants(db, a.id)

    assert {d.id for d in descendants} == {b.id, c.id}


# --- Processing-event field round-trip (task section 26) ----------------


def test_processing_event_retains_every_documented_field(db) -> None:
    case = _make_case(db)
    evidence = _make_evidence(db, case)
    artifact = _make_artifact(db, evidence, artifact_type="master", path="/a")

    event = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.EXTRACTION.value,
        actor="RecordingManager",
        actor_type=ActorType.SYSTEM,
        tool="ffmpeg",
        tool_version="n8.1.2",
        software_version="0.1.0",
        parameters={"crf": 23, "preset": "veryfast"},
        output_artifact_ids=[artifact.id],
        started_at=_T0,
        completed_at=_T0 + timedelta(seconds=5),
        status=JobStatus.COMPLETED,
        warnings=["no audio track found"],
        notes="synthetic test event",
    )

    assert event.operation == "extraction"
    assert event.actor == "RecordingManager"
    assert event.actor_type == "system"
    assert event.tool == "ffmpeg"
    assert event.tool_version == "n8.1.2"
    assert event.software_version == "0.1.0"
    assert event.started_at is not None
    assert event.completed_at is not None
    assert event.status == "completed"
    import json

    assert json.loads(event.parameters) == {"crf": 23, "preset": "veryfast"}
    assert json.loads(event.output_artifact_ids) == [artifact.id]
    assert json.loads(event.warnings) == ["no audio track found"]
    assert event.notes == "synthetic test event"
    # Phase 16: sealed into the hash chain at creation time.
    assert event.previous_hash is not None
    assert event.current_hash is not None


def test_processing_event_never_claims_human_for_a_system_actor(db) -> None:
    case = _make_case(db)
    event = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        operation=ProcessingOperation.RECOVERY.value,
        actor="RecoveryEngine",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )
    assert event.actor_type == ActorType.SYSTEM.value
    assert event.actor_type != ActorType.HUMAN.value


def test_processing_event_can_record_a_human_actor(db) -> None:
    case = _make_case(db)
    event = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        operation=CustodyEventType.EVIDENCE_RECEIVED.value,
        actor="Examiner Jane Doe",
        actor_type=ActorType.HUMAN,
        status=JobStatus.COMPLETED,
    )
    assert event.actor_type == ActorType.HUMAN.value


# --- Multiple inputs/outputs (task section 27) ---------------------------


def test_multi_input_multi_output_event(db) -> None:
    case = _make_case(db)
    evidence = _make_evidence(db, case)
    input_a = _make_artifact(db, evidence, artifact_type="stream_a", path="/in_a")
    input_b = _make_artifact(db, evidence, artifact_type="stream_b", path="/in_b")

    event = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.EXTRACTION.value,
        actor="RecordingManager",
        actor_type=ActorType.SYSTEM,
        input_artifact_ids=[input_a.id, input_b.id],
        status=JobStatus.PENDING,
    )
    output_c = _make_artifact(db, evidence, artifact_type="master", path="/out_c")
    output_d = _make_artifact(db, evidence, artifact_type="preview", path="/out_d")
    # Simulate producing two outputs from two inputs in one operation --
    # recorded as a single, complete event (append-only: one INSERT).
    completed_event = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.EXTRACTION.value,
        actor="RecordingManager",
        actor_type=ActorType.SYSTEM,
        input_artifact_ids=[input_a.id, input_b.id],
        output_artifact_ids=[output_c.id, output_d.id],
        status=JobStatus.COMPLETED,
    )

    events_for_input_a = ProvenanceManager.get_processing_events_for_artifact(db, input_a.id)
    events_for_output_c = ProvenanceManager.get_processing_events_for_artifact(db, output_c.id)

    assert completed_event.id in {e.id for e in events_for_input_a}
    assert completed_event.id in {e.id for e in events_for_output_c}
    assert event.id in {e.id for e in events_for_input_a}  # the pending one too


# --- Cross-evidence safety (task section 28) ------------------------------


def test_output_artifact_from_a_different_evidence_is_rejected(db) -> None:
    case = _make_case(db)
    evidence_a = _make_evidence(db, case, evidence_id="EVID-A")
    evidence_b = _make_evidence(db, case, evidence_id="EVID-B")
    artifact_b = _make_artifact(db, evidence_b, artifact_type="x", path="/b")

    with pytest.raises(ValueError, match="belongs to evidence"):
        ProvenanceManager.record_event(
            db,
            case_id=case.id,
            evidence_id=evidence_a.id,
            operation=ProcessingOperation.EXTRACTION.value,
            actor="x",
            actor_type=ActorType.SYSTEM,
            output_artifact_ids=[artifact_b.id],
            status=JobStatus.COMPLETED,
        )


def test_artifact_from_a_different_case_is_rejected_even_without_evidence_id(db) -> None:
    case_a = _make_case(db, case_id="CASE-A")
    case_b = _make_case(db, case_id="CASE-B")
    evidence_b = _make_evidence(db, case_b, evidence_id="EVID-B")
    artifact_b = _make_artifact(db, evidence_b, artifact_type="x", path="/b")

    with pytest.raises(ValueError, match="different case"):
        ProvenanceManager.record_event(
            db,
            case_id=case_a.id,
            operation=ProcessingOperation.CORRELATION.value,
            actor="CorrelationEngine",
            actor_type=ActorType.SYSTEM,
            output_artifact_ids=[artifact_b.id],
            status=JobStatus.COMPLETED,
        )


def test_evidence_not_belonging_to_case_is_rejected(db) -> None:
    case_a = _make_case(db, case_id="CASE-A2")
    case_b = _make_case(db, case_id="CASE-B2")
    evidence_b = _make_evidence(db, case_b, evidence_id="EVID-B2")

    with pytest.raises(ValueError, match="does not belong to case"):
        ProvenanceManager.record_event(
            db,
            case_id=case_a.id,
            evidence_id=evidence_b.id,
            operation=ProcessingOperation.PARSING.value,
            actor="x",
            actor_type=ActorType.SYSTEM,
            status=JobStatus.COMPLETED,
        )


# --- Tool/version preservation (task section 31) --------------------------


def test_tool_and_version_are_never_silently_dropped(db) -> None:
    case = _make_case(db)
    event = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        operation=ProcessingOperation.AI_ANALYSIS.value,
        actor="AIManager",
        actor_type=ActorType.SYSTEM,
        tool="yolov8n.pt",
        tool_version="yolov8n",
        software_version="0.1.0",
        status=JobStatus.COMPLETED,
    )
    fetched = ProvenanceManager.get_case_history(db, case.id)[0]
    assert fetched.tool == "yolov8n.pt"
    assert fetched.tool_version == "yolov8n"
    assert fetched.software_version == "0.1.0"
    assert event.id == fetched.id


# --- Success/partial/failed/warned states (task section 32) --------------


def test_partial_and_failed_events_never_read_as_completed(db) -> None:
    case = _make_case(db)
    partial = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        operation=ProcessingOperation.RECOVERY.value,
        actor="RecoveryEngine",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.PARTIAL,
        warnings=["3 of 5 fragments recovered"],
    )
    failed = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        operation=ProcessingOperation.RECOVERY.value,
        actor="RecoveryEngine",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.FAILED,
        error="no recoverable data found",
    )

    assert partial.status == JobStatus.PARTIAL.value
    assert partial.status != JobStatus.COMPLETED.value
    assert failed.status == JobStatus.FAILED.value
    assert failed.status != JobStatus.COMPLETED.value
    assert failed.error == "no recoverable data found"


def test_completed_event_with_warnings_still_reports_completed(db) -> None:
    case = _make_case(db)
    event = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        operation=ProcessingOperation.EXTRACTION.value,
        actor="RecordingManager",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
        warnings=["no audio track found"],
    )
    assert event.status == JobStatus.COMPLETED.value
    import json

    assert json.loads(event.warnings) == ["no audio track found"]


# --- Orphan prevention (task section 33) ----------------------------------


def test_record_event_rejects_nonexistent_case(db) -> None:
    with pytest.raises(ValueError, match="Case with id"):
        ProvenanceManager.record_event(
            db,
            case_id=999999,
            operation=ProcessingOperation.EXTRACTION.value,
            actor="x",
            actor_type=ActorType.SYSTEM,
            status=JobStatus.COMPLETED,
        )


def test_record_event_rejects_nonexistent_evidence(db) -> None:
    case = _make_case(db)
    with pytest.raises(ValueError, match="Evidence with id"):
        ProvenanceManager.record_event(
            db,
            case_id=case.id,
            evidence_id=999999,
            operation=ProcessingOperation.EXTRACTION.value,
            actor="x",
            actor_type=ActorType.SYSTEM,
            status=JobStatus.COMPLETED,
        )


def test_record_event_rejects_nonexistent_job(db) -> None:
    case = _make_case(db)
    with pytest.raises(ValueError, match="Job with id"):
        ProvenanceManager.record_event(
            db,
            case_id=case.id,
            job_id=999999,
            operation=ProcessingOperation.AI_ANALYSIS.value,
            actor="x",
            actor_type=ActorType.SYSTEM,
            status=JobStatus.COMPLETED,
        )


def test_record_event_rejects_nonexistent_input_artifact(db) -> None:
    case = _make_case(db)
    with pytest.raises(ValueError, match="referenced artifact.s. not found"):
        ProvenanceManager.record_event(
            db,
            case_id=case.id,
            operation=ProcessingOperation.EXTRACTION.value,
            actor="x",
            actor_type=ActorType.SYSTEM,
            input_artifact_ids=[999999],
            status=JobStatus.COMPLETED,
        )


def test_record_event_rejects_nonexistent_output_artifact(db) -> None:
    case = _make_case(db)
    with pytest.raises(ValueError, match="referenced artifact.s. not found"):
        ProvenanceManager.record_event(
            db,
            case_id=case.id,
            operation=ProcessingOperation.EXTRACTION.value,
            actor="x",
            actor_type=ActorType.SYSTEM,
            output_artifact_ids=[999999],
            status=JobStatus.COMPLETED,
        )


def test_record_event_with_a_valid_job_links_it(db) -> None:
    case = _make_case(db)
    job = JobManager.create_job(db, case_id=case.id, job_type="ai")
    event = ProvenanceManager.record_event(
        db,
        case_id=case.id,
        job_id=job.id,
        operation=ProcessingOperation.AI_ANALYSIS.value,
        actor="AIManager",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )
    assert event.job_id == job.id


# --- Case summary / observability -----------------------------------------


def test_case_summary_reports_counts_and_tools(db) -> None:
    case = _make_case(db)
    evidence = _make_evidence(db, case)
    artifact = _make_artifact(db, evidence, artifact_type="master", path="/a")
    ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.EXTRACTION.value,
        actor="RecordingManager",
        actor_type=ActorType.SYSTEM,
        tool="ffmpeg",
        output_artifact_ids=[artifact.id],
        status=JobStatus.COMPLETED,
    )

    summary = ProvenanceManager.get_case_summary(db, case.id)

    assert summary.case_id == case.id
    assert summary.processing_event_count == 1
    assert summary.artifact_count == 1
    assert summary.tools_used == ["ffmpeg"]
    assert summary.last_event is not None
