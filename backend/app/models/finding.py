"""
SQLAlchemy ORM model for forensic findings (Phase 22, "Automatic Evidence
Processing, Findings & Officer Notifications").

A `Finding` is a structured, review-level summary the automatic processing
orchestrator (`app.core.processing_orchestrator.ProcessingOrchestrator`)
and its findings engine (`app.core.findings_engine.FindingsEngine`) write
when an already-computed result (a hash mismatch, a partial recovery, an
AI detection, an invalid audit chain, ...) is worth an examiner's
attention. It never reimplements or recomputes the underlying analysis --
every finding traces back to the `Job`/`ProcessingEvent`/result row that
produced it via `source_job_id`/`source_reference` (Master Specification
Section 51's traceability rule, applied here to findings the same way it
already applies to AI results and recovery results).

Deliberately NOT free text: `finding_type` is a closed `FindingType`
vocabulary so the officer never has to remember which of a dozen backend
APIs might hold a result worth reviewing (this phase's own stated
objective) -- everything worth surfacing becomes one of these rows,
listed through one API.

Severity is how urgently an examiner should look, never a certainty
score (task Phase 22 scope, "Severity"/"Finding Confidence" sections):
a `CRITICAL`-severity `AUDIT_CHAIN_INVALID` finding does not mean an
officer is guilty of anything, only that the chain needs urgent
inspection. `confidence` is a separate, orthogonal axis reusing the same
closed vocabulary Phase 11 already established for timestamp
normalization (`VERIFIED`/`UNVERIFIED`/`PARTIAL`/`UNKNOWN`), plus
`NOT_APPLICABLE` for findings where "confidence" does not apply at all
(e.g. "validation requires a ground-truth dataset").

Append-oriented lifecycle, never deleted (task Phase 22 scope, "Finding
Lifecycle": "Do not delete historical findings. Resolution/dismissal must
remain auditable."): `status` moves through `FindingStatus`'s states,
recorded via `resolved_at`/`resolved_by`/`resolution_notes`, but the row
itself is never removed.

Deduplication (task Phase 22 scope, "Finding Deduplication"): repeated
findings of the identical type/scope while the underlying condition is
still open are merged into the same row (`occurrence_count` incremented,
`source_reference` extended) by `FindingsEngine`, rather than flooding the
officer with near-duplicate notifications -- the underlying analytical
results referenced by `source_reference` are never discarded, only the
review-level summary is deduplicated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.evidence import Evidence
    from app.models.job import Job
    from app.models.notification import Notification
    from app.models.recording import Recording

__all__ = ["Finding", "FindingConfidence", "FindingSeverity", "FindingStatus", "FindingType"]


class FindingType(str, Enum):
    """Closed vocabulary of finding kinds this backend can substantiate.

    Every value here has a concrete, already-implemented subsystem behind
    it (task Phase 22 scope, "Finding Types": "Only add types when a
    concrete existing subsystem can produce evidence for them") --
    listed in the comment beside each value.
    """

    #: `app.integrity.hash_verification.IntegrityManager.verify_evidence`.
    INTEGRITY_MISMATCH = "integrity_mismatch"
    #: `app.core.timestamp_manager.TimestampManager.normalize_recording`.
    TIMESTAMP_INCONSISTENCY = "timestamp_inconsistency"
    #: Recording start/end ordering or an unexplained inter-recording gap.
    POTENTIAL_RECORDING_GAP = "potential_recording_gap"
    #: `app.core.recovery_manager.RecoveryManager.run_recovery` status `partial`.
    PARTIAL_RECOVERY = "partial_recovery"
    #: A recovery attempt that succeeded but carries a caveat (e.g. low
    #: frame continuity/confidence) worth flagging without calling it partial.
    RECOVERY_WARNING = "recovery_warning"
    #: Recovery is technically available for this evidence but the active
    #: processing policy did not run it automatically (task Phase 22
    #: scope, "Recovery Automation": never silently skip without saying so).
    RECOVERY_AVAILABLE_FOR_REVIEW = "recovery_available_for_review"
    #: `app.core.recording_manager.RecordingManager.extract_recording`
    #: extraction_status `failed`/`partial` from a real parse/mux error.
    CORRUPTED_RECORDING = "corrupted_recording"
    #: `app.core.recording_manager.RecordingManager.enumerate_recordings`
    #: returning no recordings for evidence that declared a native export.
    UNSUPPORTED_FORMAT = "unsupported_format"
    #: `app.core.ai_manager.AIManager` object/face detections.
    AI_DETECTION = "ai_detection"
    #: `app.core.ai_manager.AIManager` motion events.
    AI_MOTION_EVENT = "ai_motion_event"
    #: `app.core.correlation_manager.CorrelationManager.run_correlation`.
    CROSS_CAMERA_CORRELATION = "cross_camera_correlation"
    #: `app.core.validation_manager.ValidationManager.run_validation` metric
    #: below its own recorded threshold.
    VALIDATION_FAILURE = "validation_failure"
    #: No ground-truth dataset configured for this case -- validation was
    #: never fabricated, never silently treated as "passed".
    VALIDATION_NOT_RUN = "validation_not_run"
    #: Any pipeline stage the orchestrator ran that ended `FAILED`.
    PROCESSING_FAILURE = "processing_failure"
    #: `app.core.blockchain_manager.BlockchainManager.verify_anchor`.
    BLOCKCHAIN_VERIFICATION_FAILURE = "blockchain_verification_failure"
    #: `app.core.audit_chain_manager.AuditChainManager.verify_case_chain`.
    AUDIT_CHAIN_INVALID = "audit_chain_invalid"
    #: `app.core.custody_manager.CustodyManager` custody-history exceptions
    #: (e.g. a rejected/expired handoff) surfaced for examiner attention.
    CUSTODY_EXCEPTION = "custody_exception"


class FindingSeverity(str, Enum):
    """How urgently an examiner should inspect a finding -- never a
    certainty/guilt score (task Phase 22 scope, "Severity")."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(str, Enum):
    """Reviewable lifecycle (task Phase 22 scope, "Finding Lifecycle").
    Never deleted -- only ever moves forward through these states."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class FindingConfidence(str, Enum):
    """Reuses `app.timeline.NormalizationStatus`'s vocabulary (task Phase
    22 scope, "Finding Confidence": "Do not create a second incompatible
    confidence framework") plus `NOT_APPLICABLE` for findings where a
    confidence axis does not apply at all (e.g. an absent-dataset
    notice). Never itself proof -- "confidence" describes how well this
    finding's own signal is established, not whether its real-world
    interpretation is correct."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class Finding(Base):
    """One review-level forensic finding surfaced by automatic processing.

    `source_reference` is a JSON-encoded object of whatever underlying
    result IDs substantiate this finding (e.g.
    `{"ai_result_ids": [12, 13], "recording_id": 4}`) -- deduplication
    merges into this field rather than discarding earlier evidence.
    `limitations` is a JSON-encoded list of short caveat strings (task
    Phase 22 scope, "Finding" fields: "limitations/warnings").
    """

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recording_id: Mapped[int | None] = mapped_column(
        ForeignKey("recordings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    finding_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=FindingStatus.OPEN.value, index=True
    )
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[Case] = relationship("Case")
    evidence: Mapped[Evidence | None] = relationship("Evidence")
    recording: Mapped[Recording | None] = relationship("Recording")
    source_job: Mapped[Job | None] = relationship("Job")
    notifications: Mapped[list[Notification]] = relationship(
        "Notification", back_populates="finding", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Finding finding_type={self.finding_type!r} severity={self.severity!r}>"
