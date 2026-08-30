"""Shared test fixture: a synthetic case exercising every Phase 18 report
section at once (evidence, acquisition, identification, recordings,
recovery, timeline, correlation, AI, validation, provenance, audit,
blockchain). Every row is inserted directly via the ORM (matching the
established pattern in `tests/test_ai_manager.py` etc.) rather than
running the real pipelines -- this module exists purely to give the
reporting tests something rich and deterministic to assemble from.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.audit import ActorType, ProcessingOperation
from app.blockchain.provider import LocalTestBlockchainProvider
from app.core.blockchain_manager import BlockchainManager
from app.core.case_manager import CaseManager
from app.core.job_manager import JobManager
from app.core.provenance_manager import ProvenanceManager
from app.models import (
    AIResult,
    AITrack,
    Artifact,
    Case,
    Device,
    Evidence,
    EvidenceHash,
    GroundTruth,
    JobStatus,
    MotionEvent,
    Recording,
    RecordingMetadata,
    RecoveryResult,
    Storage,
    TimelineEvent,
    ValidationMetric,
)
from app.schemas.case import CaseCreateRequest

_T0 = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)


@dataclass
class RichCase:
    case: Case
    evidence: Evidence
    recording: Recording
    master_artifact: Artifact
    preview_artifact: Artifact
    recovery: RecoveryResult
    correlated_event_id: int
    blockchain_provider: LocalTestBlockchainProvider


def build_rich_case(db: Session, *, case_id: str = "CASE-REPORT-1") -> RichCase:
    case = CaseManager.create_case(
        db, CaseCreateRequest(case_id=case_id, name="Report test case", examiner="J. Examiner")
    )

    evidence = Evidence(
        evidence_id=f"EVID-{case_id}",
        case_id=case.id,
        source_type="native_export",
        source_description="CP Plus native export",
        status="registered",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    db.add(
        EvidenceHash(
            evidence_id=evidence.id,
            algorithm="sha256",
            hash_value="a" * 64,
            software_version="0.1.0",
            verification_status="verified",
        )
    )

    db.add(
        Storage(
            evidence_id=evidence.id,
            manufacturer="Generic",
            model="USB-SSD",
            capacity_bytes=1_000_000_000,
            image_format="raw",
            read_only=True,
            status="acquired",
        )
    )

    db.add(
        Device(
            evidence_id=evidence.id,
            vendor="CP Plus",
            model="CP-UVR-0801E1-I",
            firmware="v3.1",
            device_type="NVR",
            camera_count=4,
            confidence=0.95,
            identification_method="signature_match",
        )
    )
    db.commit()

    master_artifact = Artifact(
        evidence_id=evidence.id,
        artifact_type="cp_plus_hevc_master_mp4",
        path=f"/artifacts/{case_id}/master.mp4",
        sha256="b" * 64,
        status="registered",
    )
    preview_artifact = Artifact(
        evidence_id=evidence.id,
        artifact_type="cp_plus_h264_preview_mp4",
        path=f"/artifacts/{case_id}/preview.mp4",
        sha256="c" * 64,
        status="registered",
    )
    db.add(master_artifact)
    db.add(preview_artifact)
    db.commit()
    db.refresh(master_artifact)
    db.refresh(preview_artifact)

    recording = Recording(
        evidence_id=evidence.id,
        recording_id=f"REC-{case_id}-CH1",
        camera_id="CH1",
        channel=1,
        start_original=_T0,
        end_original=_T0,
        start_normalized=_T0,
        end_normalized=_T0,
        duration_ms=60000,
        codec="hevc",
        container="mp4",
        width=1920,
        height=1080,
        fps=25.0,
        recovery_status="full",
        confidence=0.9,
        artifact_id=str(master_artifact.id),
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)

    db.add(
        RecordingMetadata(
            recording_id=recording.id,
            key="preview_artifact_id",
            value=str(preview_artifact.id),
            source="RecordingManager",
        )
    )
    db.add(
        RecordingMetadata(
            recording_id=recording.id,
            key="timestamp_status",
            value="raw_counter_unvalidated",
            source="CPPlusParser",
        )
    )
    db.commit()

    recovery = RecoveryResult(
        evidence_id=evidence.id,
        recording_id=recording.id,
        artifact_id=master_artifact.id,
        method="carving",
        status="partial",
        fragments_found=10,
        fragments_used=8,
        fragments_missing=2,
        frames_expected=1500,
        frames_recovered=1200,
        recovery_rate=0.8,
        confidence=0.7,
        recovery_engine_version="0.1.0",
        notes="RECOVERY FRAMEWORK / UNVALIDATED PATH: no real deleted-record fixture used.",
    )
    db.add(recovery)
    db.commit()
    db.refresh(recovery)

    event_a = TimelineEvent(
        case_id=case.id,
        recording_id=recording.id,
        camera_id="CH1",
        event_type="recording_start",
        original_timestamp=_T0,
        normalized_timestamp=_T0,
        confidence=0.9,
        source="recording_metadata",
        recovery_status="full",
    )
    event_b = TimelineEvent(
        case_id=case.id,
        recording_id=recording.id,
        camera_id="CH2",
        event_type="recording_start",
        original_timestamp=_T0,
        normalized_timestamp=_T0,
        confidence=0.85,
        source="recording_metadata",
        recovery_status="full",
    )
    db.add(event_a)
    db.add(event_b)
    db.commit()
    db.refresh(event_a)
    db.refresh(event_b)

    correlated = TimelineEvent(
        case_id=case.id,
        recording_id=None,
        camera_id=None,
        event_type="correlated_event",
        normalized_timestamp=_T0,
        confidence=0.8,
        source="correlation_engine",
        recovery_status="full",
        description="CH1 and CH2 recording starts within threshold",
    )
    db.add(correlated)
    db.commit()
    db.refresh(correlated)
    event_a.correlation_id = correlated.id
    event_b.correlation_id = correlated.id
    db.commit()

    db.add(
        AIResult(
            case_id=case.id,
            recording_id=recording.id,
            analysis_type="object_detection",
            model_name="yolov8n.pt",
            model_version="yolov8n",
            frame_number=10,
            timestamp=_T0,
            class_name="person",
            confidence=0.87,
            bbox_x_min=0.1,
            bbox_y_min=0.1,
            bbox_x_max=0.4,
            bbox_y_max=0.9,
            source_artifact=master_artifact.id,
        )
    )
    db.add(
        AITrack(
            case_id=case.id,
            recording_id=recording.id,
            camera_id="CH1",
            track_id=1,
            class_name="person",
            first_seen=_T0,
            last_seen=_T0,
            first_seen_frame=10,
            last_seen_frame=40,
            frame_count=30,
            average_confidence=0.85,
            model_version="yolov8n",
            tracker_version="bytetrack",
            source_artifact=master_artifact.id,
        )
    )
    db.add(
        MotionEvent(
            case_id=case.id,
            recording_id=recording.id,
            camera_id="CH1",
            start_time=_T0,
            end_time=_T0,
            score=0.6,
            method="frame_differencing",
            source_artifact=master_artifact.id,
        )
    )
    db.commit()

    ground_truth = GroundTruth(
        case_id=case.id,
        dataset_id="DS-REAL-CPPLUS",
        recording_id=recording.id,
        camera_id="CH1",
        event_type="object_detection",
        object_class="person",
        timestamp=_T0,
    )
    db.add(ground_truth)
    db.commit()

    ProvenanceManager.record_event(
        db,
        case_id=case.id,
        evidence_id=evidence.id,
        operation=ProcessingOperation.PARSING.value,
        actor="CPPlusParser",
        actor_type=ActorType.SYSTEM,
        tool="CPPlusParser",
        tool_version="0.2.0",
        status=JobStatus.COMPLETED,
    )
    validation_job = JobManager.create_job(db, case_id=case.id, job_type="validation")
    ProvenanceManager.record_event(
        db,
        case_id=case.id,
        job_id=validation_job.id,
        operation=ProcessingOperation.VALIDATION.value,
        actor="ValidationManager",
        actor_type=ActorType.SYSTEM,
        status=JobStatus.COMPLETED,
    )
    db.add(
        ValidationMetric(
            job_id=validation_job.id,
            case_id=case.id,
            dataset_id="DS-REAL-CPPLUS",
            validation_type="detection",
            metric_name="precision",
            metric_value=0.9,
            numerator=9,
            denominator=10,
        )
    )
    db.commit()

    provider = LocalTestBlockchainProvider()
    BlockchainManager.create_anchor(db, case_id=case.id, provider=provider, reason="test")

    return RichCase(
        case=case,
        evidence=evidence,
        recording=recording,
        master_artifact=master_artifact,
        preview_artifact=preview_artifact,
        recovery=recovery,
        correlated_event_id=correlated.id,
        blockchain_provider=provider,
    )
