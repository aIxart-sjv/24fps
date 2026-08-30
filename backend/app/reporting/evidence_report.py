"""
Standardized report content assembly (Phase 18).
Master Specification Section 43 ("Reporting Engine"), Section 44
("Forensic Report Content").

This module defines the report's canonical content model (`ReportData`
and its section dataclasses) and `assemble_report_data`, which builds
that model by reading -- never recomputing or reinterpreting -- existing
case state through Phases 1-17's own persisted results and, where one
already exists, their own manager's read-only listing method (e.g.
`ProvenanceManager.get_case_history`, `AuditChainManager.
verify_case_chain`, `BlockchainManager.list_anchors`). Where no
dedicated read-only lister exists (Device/Storage/EvidenceHash/Recording/
RecoveryResult/TimelineEvent/AIResult/AITrack/MotionEvent/
ValidationMetric), this module queries those tables directly and
ordered by primary key ascending, exactly like every prior phase's own
manager already does for its own case-scoped listings (Section 51 rule:
"Do not generate reports from nondeterministic database order" -- task
Phase 18 scope's own restatement of the same rule Phase 16/17 already
established for chain ordering).

Every value that reaches a `ReportData` field is either:
- a source fact read verbatim from a persisted row (never recomputed),
- a genuinely derived-but-transparent label this module computes
  *from already-persisted fields* (e.g. classifying a recovery result's
  own `notes` text, or a provider name), always documented at its call
  site, or
- an explicit `None`/empty list when nothing exists -- never a fabricated
  placeholder value.

This module never calls into `app.recovery`, `app.timeline`, `app.ai`,
`app.validation`, `app.adapters`, or any acquisition/parsing/decoding
code -- it only reads what those phases have already written to the
database. It never mutates anything (no `db.add`/`db.commit` anywhere in
this file).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.audit.hash_chain import CHAIN_ALGORITHM
from app.core.audit_chain_manager import AuditChainManager
from app.core.blockchain_manager import BlockchainManager
from app.core.provenance_manager import ProvenanceManager
from app.core.timeline_manager import CORRELATED_EVENT
from app.models import (
    AIResult,
    AITrack,
    Artifact,
    Case,
    Device,
    Evidence,
    EvidenceHash,
    Finding,
    MotionEvent,
    Recording,
    RecordingMetadata,
    Report,
    RecoveryResult,
    Storage,
    TimelineEvent,
    ValidationMetric,
)

__all__ = [
    "REPORT_SCHEMA_VERSION",
    "AISection",
    "AcquisitionEntry",
    "AuditChainSection",
    "BlockchainAnchorEntry",
    "CaseSummarySection",
    "CorrelationEntry",
    "EvidenceEntry",
    "FindingEntry",
    "HashEntry",
    "IdentificationEntry",
    "LimitationEntry",
    "ProvenanceEventEntry",
    "RecordingEntry",
    "RecoveryEntry",
    "ReportData",
    "ReportMetadata",
    "TimelineEntry",
    "TrackEntry",
    "ValidationMetricEntry",
    "assemble_report_data",
]

#: Independent of `software_version` and any parser/model version --
#: bumped only when the *shape* of `ReportData`/the rendered report
#: changes (task Phase 18 scope section 4).
REPORT_SCHEMA_VERSION = "1.0"


def _iso(value: datetime | None) -> str | None:
    """Deterministic UTC ISO-8601 formatting, reusing the same
    naive-treated-as-UTC convention established in `app.audit.hash_chain
    ._canonical_datetime` and `app.core.validation_manager` -- every
    `DateTime(timezone=True)` column in this codebase round-trips through
    SQLite as timezone-naive."""
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()


def _json_list(value: str | None) -> list[object] | None:
    if value is None:
        return None
    return json.loads(value)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Section dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportMetadata:
    """Task Phase 18 scope section 4: schema version, software version,
    parser/model versions, and generation time are kept explicitly
    distinct from one another (parser/model versions live on the
    individual section entries that used them, not here)."""

    report_schema_version: str
    software_version: str | None
    generated_at: str
    case_id: int
    case_identifier: str


@dataclass(frozen=True)
class CaseSummarySection:
    case_id: int
    case_identifier: str
    case_number: str | None
    name: str
    description: str | None
    examiner: str | None
    status: str
    created_at: str | None
    updated_at: str | None
    evidence_count: int
    recording_count: int
    recovery_result_count: int
    ai_result_count: int
    ai_track_count: int
    motion_event_count: int
    validation_metric_count: int
    correlation_event_count: int
    timeline_event_count: int
    processing_event_count: int
    blockchain_anchor_count: int
    report_count: int


@dataclass(frozen=True)
class HashEntry:
    algorithm: str
    hash_value: str
    calculated_at: str | None
    verification_status: str
    software_version: str | None


@dataclass(frozen=True)
class EvidenceEntry:
    evidence_id: int
    evidence_identifier: str
    source_type: str
    source_description: str | None
    status: str
    created_at: str | None
    hashes: list[HashEntry]
    artifact_count: int
    recording_count: int
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AcquisitionEntry:
    """Storage-image acquisition facts (Phase 5). Absent (`storage_present
    = False`) for evidence registered as a native export with no imaged
    storage device -- never fabricated."""

    evidence_id: int
    storage_present: bool
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    capacity_bytes: int | None
    sector_size: int | None
    interface: str | None
    image_format: str | None
    image_path: str | None
    read_only: bool | None
    status: str | None


@dataclass(frozen=True)
class IdentificationEntry:
    """Phase 6 device-identification facts. Absent (`device_present =
    False`) when identification has not been run for this evidence --
    never silently rerun during report generation (task Phase 18 scope
    section 8: "Prefer persisted results rather than silently rerunning
    detection")."""

    evidence_id: int
    device_present: bool
    vendor: str | None
    model: str | None
    firmware: str | None
    serial_number: str | None
    device_type: str | None
    channel_count: int | None
    camera_count: int | None
    confidence: float | None
    identification_method: str | None


@dataclass(frozen=True)
class RecordingEntry:
    """Task Phase 18 scope section 9: the CPV source / H.265 master /
    H.264 preview distinction is preserved explicitly -- `master_*` is
    the authoritative recording artifact; `preview_*` is a transcoded
    convenience copy, never described as authoritative."""

    recording_id: int
    recording_identifier: str
    evidence_id: int
    camera_id: str | None
    channel: int | None
    start_original: str | None
    end_original: str | None
    start_normalized: str | None
    end_normalized: str | None
    duration_ms: int | None
    codec: str | None
    container: str | None
    width: int | None
    height: int | None
    fps: float | None
    recovery_status: str | None
    recovery_method: str | None
    confidence: float | None
    master_artifact_id: int | None
    master_artifact_path: str | None
    master_artifact_type: str | None
    preview_artifact_id: int | None
    preview_artifact_path: str | None
    preview_artifact_type: str | None
    metadata_entries: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryEntry:
    """Task Phase 18 scope section 10: `validation_state` distinguishes
    an implemented-but-not-independently-confirmed recovery framework
    from one Phase 14 has actually validated against real evidence.
    Derived transparently from this row's own `notes` text (the CP Plus
    deleted-recording recovery path is the only one in this codebase that
    marks itself this way today -- see `app.adapters.cp_plus.recovery`);
    never claims `VALIDATED` merely because a status is `RECOVERED`."""

    recovery_result_id: int
    evidence_id: int
    recording_id: int
    method: str
    status: str
    fragments_found: int | None
    fragments_used: int | None
    fragments_missing: int | None
    frames_expected: int | None
    frames_recovered: int | None
    recovery_rate: float | None
    timestamp_error: float | None
    frame_continuity: float | None
    confidence: float | None
    recovery_engine_version: str | None
    parser_version: str | None
    validation_state: str
    notes: str | None


@dataclass(frozen=True)
class TimelineEntry:
    event_id: int
    event_type: str
    camera_id: str | None
    recording_id: int | None
    original_timestamp: str | None
    normalized_timestamp: str | None
    source: str | None
    confidence: float | None
    description: str | None
    ai_reference: str | None
    recovery_status: str | None
    correlation_id: int | None


@dataclass(frozen=True)
class CorrelationEntry:
    """Task Phase 18 scope section 12: a correlation candidate links
    contributing source events -- it is never presented as confirmed
    identity."""

    correlated_event_id: int
    contributing_event_ids: list[int]
    camera_ids: list[str]
    normalized_timestamp: str | None
    confidence: float | None
    recovery_status: str | None
    description: str | None


@dataclass(frozen=True)
class DetectionEntry:
    detection_id: int
    recording_id: int
    analysis_type: str
    frame_number: int
    timestamp: str | None
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    model_name: str
    model_version: str
    track_id: int | None
    source_artifact_id: int
    job_id: int | None


@dataclass(frozen=True)
class TrackEntry:
    track_id_db: int
    track_id: int
    recording_id: int
    camera_id: str | None
    class_name: str
    first_seen: str | None
    last_seen: str | None
    first_seen_frame: int
    last_seen_frame: int
    frame_count: int
    average_confidence: float
    model_version: str
    tracker_version: str
    source_artifact_id: int
    job_id: int | None


@dataclass(frozen=True)
class MotionEntry:
    motion_event_id: int
    recording_id: int
    camera_id: str | None
    start_time: str | None
    end_time: str | None
    score: float | None
    method: str
    parameters: dict[str, object] | None
    source_artifact_id: int
    job_id: int | None


@dataclass(frozen=True)
class AISection:
    """Task Phase 18 scope section 13: face detection results are
    surfaced through `DetectionEntry.analysis_type == "face"` exactly as
    Phase 13 recorded them -- never elevated to identity recognition, and
    no confidence value here is recalculated."""

    detections: list[DetectionEntry] = field(default_factory=list)
    tracks: list[TrackEntry] = field(default_factory=list)
    motion_events: list[MotionEntry] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationMetricEntry:
    """Task Phase 18 scope section 14: `evidence_kind` distinguishes
    real-evidence validation from controlled/synthetic validation.
    Derived from `dataset_id`'s naming convention only (this codebase's
    own real-evidence tests use the `DS-REAL-...` prefix, e.g.
    `tests/test_cp_plus_validation_real_evidence_integration.py`) --
    there is no independent schema flag for this today, so the
    classification is a documented, transparent naming-convention
    heuristic, not a verified database fact. Always double-checked
    against the dataset_id string itself, which is also included
    verbatim so a reader can judge for themselves."""

    metric_id: int
    job_id: int
    dataset_id: str
    validation_type: str
    metric_name: str
    metric_value: float | None
    numerator: float | None
    denominator: float | None
    threshold: float | None
    evidence_kind: str
    notes: str | None
    created_at: str | None


@dataclass(frozen=True)
class ProvenanceEventEntry:
    event_id: int
    operation: str
    actor: str
    actor_type: str
    tool: str | None
    tool_version: str | None
    software_version: str | None
    status: str
    started_at: str | None
    completed_at: str | None
    input_artifact_ids: list[object] | None
    output_artifact_ids: list[object] | None
    warnings: list[object] | None
    error: str | None
    description: str | None


@dataclass(frozen=True)
class AuditChainSection:
    """Task Phase 18 scope section 16: reports the Phase 16 chain's
    *current* verification result exactly as computed -- an INVALID
    chain is never reported as VALID, and generating a report never
    itself alters the chain (this section only calls `AuditChainManager.
    verify_case_chain`, a read-only recompute-and-compare)."""

    chain_id: str
    chain_scope: str
    chain_algorithm: str
    event_count: int
    first_event_id: int | None
    last_event_id: int | None
    valid: bool
    failure_event_id: int | None
    failure_reason: str | None
    failure_detail: str | None
    checked_at: str


@dataclass(frozen=True)
class BlockchainAnchorEntry:
    """Task Phase 18 scope section 17: `is_real_network` is derived
    solely from `provider != "local_testnet"` (the only provider this
    codebase implements, per `app.blockchain.provider.
    LocalTestBlockchainProvider`) -- a local/test anchor is never
    described as a public blockchain transaction."""

    anchor_id: int
    chain_id: str
    audit_state_hash: str
    provider: str
    network: str
    transaction_reference: str
    status: str
    is_real_network: bool
    event_count: int
    last_event_id: int
    reason: str | None
    created_at: str
    verified_at: str | None


@dataclass(frozen=True)
class FindingEntry:
    """Phase 22 addition: a structured, review-level finding generated by
    `app.core.findings_engine.FindingsEngine`, carried through into the
    report exactly as recorded -- never re-derived here, and never
    presented as a stronger claim than the finding's own hedged
    description already makes (task Phase 22 scope, "Reporting
    Integration": "The report must preserve: findings, limitations,
    processing status, unresolved states")."""

    finding_id: int
    finding_type: str
    severity: str
    confidence: str
    title: str
    description: str
    status: str
    evidence_id: int | None
    recording_id: int | None
    occurrence_count: int
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class LimitationEntry:
    category: str
    description: str


@dataclass(frozen=True)
class ReportData:
    """The complete, canonical content of one standardized report."""

    metadata: ReportMetadata
    case: CaseSummarySection
    evidence: list[EvidenceEntry]
    acquisition: list[AcquisitionEntry]
    identification: list[IdentificationEntry]
    recordings: list[RecordingEntry]
    recovery: list[RecoveryEntry]
    timeline: list[TimelineEntry]
    correlation: list[CorrelationEntry]
    ai: AISection
    validation: list[ValidationMetricEntry]
    provenance: list[ProvenanceEventEntry]
    audit: AuditChainSection
    blockchain: list[BlockchainAnchorEntry]
    findings: list[FindingEntry] = field(default_factory=list)
    limitations: list[LimitationEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Assembly (read-only)
# ---------------------------------------------------------------------------


def _hash_entries(db: Session, evidence_id: int) -> list[HashEntry]:
    rows = (
        db.query(EvidenceHash)
        .filter(EvidenceHash.evidence_id == evidence_id)
        .order_by(EvidenceHash.id.asc())
        .all()
    )
    return [
        HashEntry(
            algorithm=(
                row.algorithm.value if hasattr(row.algorithm, "value") else str(row.algorithm)
            ),
            hash_value=row.hash_value,
            calculated_at=_iso(row.calculated_at),
            verification_status=(
                row.verification_status.value
                if hasattr(row.verification_status, "value")
                else str(row.verification_status)
            ),
            software_version=row.software_version,
        )
        for row in rows
    ]


def _evidence_entries(db: Session, case: Case) -> list[EvidenceEntry]:
    evidence_rows = (
        db.query(Evidence).filter(Evidence.case_id == case.id).order_by(Evidence.id.asc()).all()
    )
    entries: list[EvidenceEntry] = []
    for evidence in evidence_rows:
        artifact_count = db.query(Artifact).filter(Artifact.evidence_id == evidence.id).count()
        recording_count = db.query(Recording).filter(Recording.evidence_id == evidence.id).count()
        entries.append(
            EvidenceEntry(
                evidence_id=evidence.id,
                evidence_identifier=evidence.evidence_id,
                source_type=evidence.source_type,
                source_description=evidence.source_description,
                status=evidence.status,
                created_at=_iso(evidence.created_at),
                hashes=_hash_entries(db, evidence.id),
                artifact_count=artifact_count,
                recording_count=recording_count,
                warnings=[],
            )
        )
    return entries


def _acquisition_entries(db: Session, evidence_rows: list[Evidence]) -> list[AcquisitionEntry]:
    entries: list[AcquisitionEntry] = []
    for evidence in evidence_rows:
        storage = db.query(Storage).filter(Storage.evidence_id == evidence.id).first()
        if storage is None:
            entries.append(
                AcquisitionEntry(
                    evidence_id=evidence.id,
                    storage_present=False,
                    manufacturer=None,
                    model=None,
                    serial_number=None,
                    capacity_bytes=None,
                    sector_size=None,
                    interface=None,
                    image_format=None,
                    image_path=None,
                    read_only=None,
                    status=None,
                )
            )
            continue
        entries.append(
            AcquisitionEntry(
                evidence_id=evidence.id,
                storage_present=True,
                manufacturer=storage.manufacturer,
                model=storage.model,
                serial_number=storage.serial_number,
                capacity_bytes=storage.capacity_bytes,
                sector_size=storage.sector_size,
                interface=storage.interface,
                image_format=storage.image_format,
                image_path=storage.image_path,
                read_only=storage.read_only,
                status=storage.status,
            )
        )
    return entries


def _identification_entries(
    db: Session, evidence_rows: list[Evidence]
) -> list[IdentificationEntry]:
    entries: list[IdentificationEntry] = []
    for evidence in evidence_rows:
        device = db.query(Device).filter(Device.evidence_id == evidence.id).first()
        if device is None:
            entries.append(
                IdentificationEntry(
                    evidence_id=evidence.id,
                    device_present=False,
                    vendor=None,
                    model=None,
                    firmware=None,
                    serial_number=None,
                    device_type=None,
                    channel_count=None,
                    camera_count=None,
                    confidence=None,
                    identification_method=None,
                )
            )
            continue
        entries.append(
            IdentificationEntry(
                evidence_id=evidence.id,
                device_present=True,
                vendor=device.vendor,
                model=device.model,
                firmware=device.firmware,
                serial_number=device.serial_number,
                device_type=device.device_type,
                channel_count=device.channel_count,
                camera_count=device.camera_count,
                confidence=device.confidence,
                identification_method=device.identification_method,
            )
        )
    return entries


def _recording_entries(db: Session, evidence_rows: list[Evidence]) -> list[RecordingEntry]:
    entries: list[RecordingEntry] = []
    evidence_ids = [e.id for e in evidence_rows]
    if not evidence_ids:
        return entries
    recordings = (
        db.query(Recording)
        .filter(Recording.evidence_id.in_(evidence_ids))
        .order_by(Recording.id.asc())
        .all()
    )
    for recording in recordings:
        master_id = int(recording.artifact_id) if recording.artifact_id else None
        master_artifact = (
            db.query(Artifact).filter(Artifact.id == master_id).first()
            if master_id is not None
            else None
        )

        metadata_rows = (
            db.query(RecordingMetadata)
            .filter(RecordingMetadata.recording_id == recording.id)
            .order_by(RecordingMetadata.id.asc())
            .all()
        )
        metadata_entries = {row.key: row.value for row in metadata_rows if row.value is not None}

        preview_id: int | None = None
        preview_row = next((r for r in metadata_rows if r.key == "preview_artifact_id"), None)
        if preview_row is not None and preview_row.value is not None:
            preview_id = int(preview_row.value)
        preview_artifact = (
            db.query(Artifact).filter(Artifact.id == preview_id).first()
            if preview_id is not None
            else None
        )

        entries.append(
            RecordingEntry(
                recording_id=recording.id,
                recording_identifier=recording.recording_id,
                evidence_id=recording.evidence_id,
                camera_id=recording.camera_id,
                channel=recording.channel,
                start_original=_iso(recording.start_original),
                end_original=_iso(recording.end_original),
                start_normalized=_iso(recording.start_normalized),
                end_normalized=_iso(recording.end_normalized),
                duration_ms=recording.duration_ms,
                codec=recording.codec,
                container=recording.container,
                width=recording.width,
                height=recording.height,
                fps=recording.fps,
                recovery_status=recording.recovery_status,
                recovery_method=recording.recovery_method,
                confidence=recording.confidence,
                master_artifact_id=master_artifact.id if master_artifact else None,
                master_artifact_path=master_artifact.path if master_artifact else None,
                master_artifact_type=master_artifact.artifact_type if master_artifact else None,
                preview_artifact_id=preview_artifact.id if preview_artifact else None,
                preview_artifact_path=preview_artifact.path if preview_artifact else None,
                preview_artifact_type=preview_artifact.artifact_type if preview_artifact else None,
                metadata_entries=metadata_entries,
            )
        )
    return entries


def _classify_recovery_validation_state(notes: str | None) -> str:
    """Documented heuristic (see `RecoveryEntry`'s docstring): text-marked
    unvalidated-framework paths are labeled as such; everything else
    defaults to the conservative "not independently validated" label --
    never "validated" merely because a status looks successful."""
    if notes and "unvalidated" in notes.lower():
        return "unvalidated_framework"
    return "not_independently_validated"


def _recovery_entries(db: Session, evidence_rows: list[Evidence]) -> list[RecoveryEntry]:
    entries: list[RecoveryEntry] = []
    evidence_ids = [e.id for e in evidence_rows]
    if not evidence_ids:
        return entries
    rows = (
        db.query(RecoveryResult)
        .filter(RecoveryResult.evidence_id.in_(evidence_ids))
        .order_by(RecoveryResult.id.asc())
        .all()
    )
    for row in rows:
        entries.append(
            RecoveryEntry(
                recovery_result_id=row.id,
                evidence_id=row.evidence_id,
                recording_id=row.recording_id,
                method=row.method,
                status=row.status,
                fragments_found=row.fragments_found,
                fragments_used=row.fragments_used,
                fragments_missing=row.fragments_missing,
                frames_expected=row.frames_expected,
                frames_recovered=row.frames_recovered,
                recovery_rate=row.recovery_rate,
                timestamp_error=row.timestamp_error,
                frame_continuity=row.frame_continuity,
                confidence=row.confidence,
                recovery_engine_version=row.recovery_engine_version,
                parser_version=row.parser_version,
                validation_state=_classify_recovery_validation_state(row.notes),
                notes=row.notes,
            )
        )
    return entries


def _timeline_entries(db: Session, case_id: int) -> list[TimelineEntry]:
    rows = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.case_id == case_id)
        .order_by(TimelineEvent.id.asc())
        .all()
    )
    return [
        TimelineEntry(
            event_id=row.id,
            event_type=row.event_type,
            camera_id=row.camera_id,
            recording_id=row.recording_id,
            original_timestamp=_iso(row.original_timestamp),
            normalized_timestamp=_iso(row.normalized_timestamp),
            source=row.source,
            confidence=row.confidence,
            description=row.description,
            ai_reference=row.ai_reference,
            recovery_status=row.recovery_status,
            correlation_id=row.correlation_id,
        )
        for row in rows
    ]


def _correlation_entries(db: Session, case_id: int) -> list[CorrelationEntry]:
    correlated_rows = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.case_id == case_id, TimelineEvent.event_type == CORRELATED_EVENT)
        .order_by(TimelineEvent.id.asc())
        .all()
    )
    entries: list[CorrelationEntry] = []
    for row in correlated_rows:
        source_rows = (
            db.query(TimelineEvent)
            .filter(TimelineEvent.correlation_id == row.id)
            .order_by(TimelineEvent.id.asc())
            .all()
        )
        camera_ids = sorted({s.camera_id for s in source_rows if s.camera_id is not None})
        entries.append(
            CorrelationEntry(
                correlated_event_id=row.id,
                contributing_event_ids=[s.id for s in source_rows],
                camera_ids=camera_ids,
                normalized_timestamp=_iso(row.normalized_timestamp),
                confidence=row.confidence,
                recovery_status=row.recovery_status,
                description=row.description,
            )
        )
    return entries


def _ai_section(db: Session, case_id: int) -> AISection:
    detections = (
        db.query(AIResult).filter(AIResult.case_id == case_id).order_by(AIResult.id.asc()).all()
    )
    tracks = db.query(AITrack).filter(AITrack.case_id == case_id).order_by(AITrack.id.asc()).all()
    motion = (
        db.query(MotionEvent)
        .filter(MotionEvent.case_id == case_id)
        .order_by(MotionEvent.id.asc())
        .all()
    )
    return AISection(
        detections=[
            DetectionEntry(
                detection_id=d.id,
                recording_id=d.recording_id,
                analysis_type=d.analysis_type,
                frame_number=d.frame_number,
                timestamp=_iso(d.timestamp),
                class_name=d.class_name,
                confidence=d.confidence,
                bbox=(d.bbox_x_min, d.bbox_y_min, d.bbox_x_max, d.bbox_y_max),
                model_name=d.model_name,
                model_version=d.model_version,
                track_id=d.track_id,
                source_artifact_id=d.source_artifact,
                job_id=d.job_id,
            )
            for d in detections
        ],
        tracks=[
            TrackEntry(
                track_id_db=t.id,
                track_id=t.track_id,
                recording_id=t.recording_id,
                camera_id=t.camera_id,
                class_name=t.class_name,
                first_seen=_iso(t.first_seen),
                last_seen=_iso(t.last_seen),
                first_seen_frame=t.first_seen_frame,
                last_seen_frame=t.last_seen_frame,
                frame_count=t.frame_count,
                average_confidence=t.average_confidence,
                model_version=t.model_version,
                tracker_version=t.tracker_version,
                source_artifact_id=t.source_artifact,
                job_id=t.job_id,
            )
            for t in tracks
        ],
        motion_events=[
            MotionEntry(
                motion_event_id=m.id,
                recording_id=m.recording_id,
                camera_id=m.camera_id,
                start_time=_iso(m.start_time),
                end_time=_iso(m.end_time),
                score=m.score,
                method=m.method,
                parameters=json.loads(m.parameters) if m.parameters else None,
                source_artifact_id=m.source_artifact,
                job_id=m.job_id,
            )
            for m in motion
        ],
    )


def _classify_validation_evidence_kind(dataset_id: str) -> str:
    """Documented naming-convention heuristic -- see
    `ValidationMetricEntry`'s docstring. Not an independently verified
    database fact."""
    if dataset_id.upper().startswith("DS-REAL-") or "real" in dataset_id.lower():
        return "real_evidence"
    return "controlled_synthetic"


def _validation_entries(db: Session, case_id: int) -> list[ValidationMetricEntry]:
    rows = (
        db.query(ValidationMetric)
        .filter(ValidationMetric.case_id == case_id)
        .order_by(ValidationMetric.id.asc())
        .all()
    )
    return [
        ValidationMetricEntry(
            metric_id=row.id,
            job_id=row.job_id,
            dataset_id=row.dataset_id,
            validation_type=row.validation_type,
            metric_name=row.metric_name,
            metric_value=row.metric_value,
            numerator=row.numerator,
            denominator=row.denominator,
            threshold=row.threshold,
            evidence_kind=_classify_validation_evidence_kind(row.dataset_id),
            notes=row.notes,
            created_at=_iso(row.created_at),
        )
        for row in rows
    ]


def _provenance_entries(db: Session, case_id: int) -> list[ProvenanceEventEntry]:
    events = ProvenanceManager.get_case_history(db, case_id)
    return [
        ProvenanceEventEntry(
            event_id=e.id,
            operation=e.operation,
            actor=e.actor,
            actor_type=e.actor_type,
            tool=e.tool,
            tool_version=e.tool_version,
            software_version=e.software_version,
            status=e.status,
            started_at=_iso(e.started_at),
            completed_at=_iso(e.completed_at),
            input_artifact_ids=_json_list(e.input_artifact_ids),
            output_artifact_ids=_json_list(e.output_artifact_ids),
            warnings=_json_list(e.warnings),
            error=e.error,
            description=e.description,
        )
        for e in events
    ]


def _audit_section(db: Session, case_id: int) -> AuditChainSection:
    result = AuditChainManager.verify_case_chain(db, case_id)
    failure = result.failure
    return AuditChainSection(
        chain_id=f"case-{case_id}",
        chain_scope=result.chain_scope,
        chain_algorithm=CHAIN_ALGORITHM,
        event_count=result.event_count,
        first_event_id=result.first_event_id,
        last_event_id=result.last_event_id,
        valid=result.valid,
        failure_event_id=failure.event_id if failure else None,
        failure_reason=failure.reason.value if failure else None,
        failure_detail=failure.detail if failure else None,
        checked_at=_iso(datetime.now(UTC)) or "",
    )


def _blockchain_entries(db: Session, case_id: int) -> list[BlockchainAnchorEntry]:
    anchors = BlockchainManager.list_anchors(db, case_id)
    return [
        BlockchainAnchorEntry(
            anchor_id=a.id,
            chain_id=a.chain_id,
            audit_state_hash=a.audit_state_hash,
            provider=a.provider,
            network=a.network,
            transaction_reference=a.transaction_reference,
            status=a.status,
            is_real_network=a.provider != "local_testnet",
            event_count=a.event_count,
            last_event_id=a.last_event_id,
            reason=a.reason,
            created_at=_iso(a.created_at) or "",
            verified_at=_iso(a.verified_at),
        )
        for a in anchors
    ]


def _finding_entries(db: Session, case_id: int) -> list[FindingEntry]:
    rows = db.query(Finding).filter(Finding.case_id == case_id).order_by(Finding.id.asc()).all()
    return [
        FindingEntry(
            finding_id=row.id,
            finding_type=row.finding_type,
            severity=row.severity,
            confidence=row.confidence,
            title=row.title,
            description=row.description,
            status=row.status,
            evidence_id=row.evidence_id,
            recording_id=row.recording_id,
            occurrence_count=row.occurrence_count,
            created_at=_iso(row.created_at),
            updated_at=_iso(row.updated_at),
        )
        for row in rows
    ]


def _build_limitations(
    *,
    recordings: list[RecordingEntry],
    recovery: list[RecoveryEntry],
    validation: list[ValidationMetricEntry],
    audit: AuditChainSection,
    blockchain: list[BlockchainAnchorEntry],
) -> list[LimitationEntry]:
    """Explicit, never-suppressed limitations (task Phase 18 scope
    section 18). Only includes a limitation category when the assembled
    content actually exhibits it -- never a boilerplate list unrelated to
    this case's real content."""
    limitations: list[LimitationEntry] = []

    for recording_entry in recordings:
        raw_status = recording_entry.metadata_entries.get("timestamp_status")
        if raw_status and "unvalidated" in raw_status.lower():
            limitations.append(
                LimitationEntry(
                    category="timestamp",
                    description=(
                        f"Recording {recording_entry.recording_identifier!r}: source timestamp "
                        f"status is {raw_status!r} -- the raw vendor timestamp meaning has not "
                        "been independently verified."
                    ),
                )
            )
        if recording_entry.preview_artifact_id is not None:
            limitations.append(
                LimitationEntry(
                    category="recording",
                    description=(
                        f"Recording {recording_entry.recording_identifier!r}: an H.264 preview "
                        "artifact exists for convenience/compatibility playback only -- the "
                        "H.265 master artifact (or the original CPV source) remains the "
                        "authoritative recording, never the preview."
                    ),
                )
            )

    for recovery_entry in recovery:
        if recovery_entry.validation_state != "validated":
            limitations.append(
                LimitationEntry(
                    category="recovery",
                    description=(
                        f"Recovery result {recovery_entry.recovery_result_id} "
                        f"(method={recovery_entry.method!r}, status={recovery_entry.status!r}) "
                        f"is {recovery_entry.validation_state!r} -- no real deleted-recording "
                        "fixture has independently confirmed this recovery path in this case."
                    ),
                )
            )

    for validation_entry in validation:
        if validation_entry.evidence_kind != "real_evidence":
            limitations.append(
                LimitationEntry(
                    category="validation",
                    description=(
                        f"Validation metric {validation_entry.metric_id} "
                        f"(dataset={validation_entry.dataset_id!r}, "
                        f"metric={validation_entry.metric_name!r}) is classified "
                        "CONTROLLED/SYNTHETIC based on dataset naming convention -- do not read "
                        "it as a production, real-world accuracy claim."
                    ),
                )
            )

    if not audit.valid:
        limitations.append(
            LimitationEntry(
                category="audit",
                description=(
                    f"The Phase 16 hash-linked audit chain for this case is currently INVALID "
                    f"(first failure at event {audit.failure_event_id}: {audit.failure_reason})."
                ),
            )
        )

    if not blockchain:
        limitations.append(
            LimitationEntry(
                category="blockchain",
                description="No blockchain anchor has been recorded for this case.",
            )
        )
    else:
        for anchor_entry in blockchain:
            if not anchor_entry.is_real_network:
                limitations.append(
                    LimitationEntry(
                        category="blockchain",
                        description=(
                            f"Anchor {anchor_entry.anchor_id} was submitted to a LOCAL/TEST "
                            f"blockchain provider ({anchor_entry.provider!r}, "
                            f"network={anchor_entry.network!r}), not a real public blockchain "
                            "network."
                        ),
                    )
                )

    return limitations


def assemble_report_data(db: Session, case: Case, *, software_version: str | None) -> ReportData:
    """Assemble the complete, canonical content of one report for `case`.

    Read-only: never writes to `db`, never recomputes recovery/timeline/
    AI/validation results, never mutates the Phase 16 audit chain or any
    Phase 17 blockchain anchor.

    Args:
        db: Database session.
        case: The case to report on. Must already exist.
        software_version: The running backend build version, stamped
            into `ReportMetadata` (distinct from the report schema
            version and from any parser/model version recorded on
            individual section entries).

    Returns:
        The assembled `ReportData`.
    """
    evidence_rows = (
        db.query(Evidence).filter(Evidence.case_id == case.id).order_by(Evidence.id.asc()).all()
    )

    recording_count = _recording_count(db, evidence_rows)
    recovery_count = _recovery_count(db, evidence_rows)
    ai_result_count = db.query(AIResult).filter(AIResult.case_id == case.id).count()
    ai_track_count = db.query(AITrack).filter(AITrack.case_id == case.id).count()
    motion_event_count = db.query(MotionEvent).filter(MotionEvent.case_id == case.id).count()
    validation_metric_count = (
        db.query(ValidationMetric).filter(ValidationMetric.case_id == case.id).count()
    )
    timeline_event_count = db.query(TimelineEvent).filter(TimelineEvent.case_id == case.id).count()
    correlation_event_count = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.case_id == case.id, TimelineEvent.event_type == CORRELATED_EVENT)
        .count()
    )
    provenance_events = _provenance_entries(db, case.id)
    blockchain_entries = _blockchain_entries(db, case.id)
    report_count = db.query(Report).filter(Report.case_id == case.id).count()

    case_section = CaseSummarySection(
        case_id=case.id,
        case_identifier=case.case_id,
        case_number=case.case_number,
        name=case.name,
        description=case.description,
        examiner=case.examiner,
        status=case.status.value if hasattr(case.status, "value") else str(case.status),
        created_at=_iso(case.created_at),
        updated_at=_iso(case.updated_at),
        evidence_count=len(evidence_rows),
        recording_count=recording_count,
        recovery_result_count=recovery_count,
        ai_result_count=ai_result_count,
        ai_track_count=ai_track_count,
        motion_event_count=motion_event_count,
        validation_metric_count=validation_metric_count,
        correlation_event_count=correlation_event_count,
        timeline_event_count=timeline_event_count,
        processing_event_count=len(provenance_events),
        blockchain_anchor_count=len(blockchain_entries),
        report_count=report_count,
    )

    recordings = _recording_entries(db, evidence_rows)
    recovery = _recovery_entries(db, evidence_rows)
    validation = _validation_entries(db, case.id)
    audit_section = _audit_section(db, case.id)

    limitations = _build_limitations(
        recordings=recordings,
        recovery=recovery,
        validation=validation,
        audit=audit_section,
        blockchain=blockchain_entries,
    )

    return ReportData(
        metadata=ReportMetadata(
            report_schema_version=REPORT_SCHEMA_VERSION,
            software_version=software_version,
            generated_at=_iso(datetime.now(UTC)) or "",
            case_id=case.id,
            case_identifier=case.case_id,
        ),
        case=case_section,
        evidence=_evidence_entries(db, case),
        acquisition=_acquisition_entries(db, evidence_rows),
        identification=_identification_entries(db, evidence_rows),
        recordings=recordings,
        recovery=recovery,
        timeline=_timeline_entries(db, case.id),
        correlation=_correlation_entries(db, case.id),
        ai=_ai_section(db, case.id),
        validation=validation,
        provenance=provenance_events,
        audit=audit_section,
        blockchain=blockchain_entries,
        findings=_finding_entries(db, case.id),
        limitations=limitations,
    )


def _recording_count(db: Session, evidence_rows: list[Evidence]) -> int:
    evidence_ids = [e.id for e in evidence_rows]
    if not evidence_ids:
        return 0
    return db.query(Recording).filter(Recording.evidence_id.in_(evidence_ids)).count()


def _recovery_count(db: Session, evidence_rows: list[Evidence]) -> int:
    evidence_ids = [e.id for e in evidence_rows]
    if not evidence_ids:
        return 0
    return db.query(RecoveryResult).filter(RecoveryResult.evidence_id.in_(evidence_ids)).count()
