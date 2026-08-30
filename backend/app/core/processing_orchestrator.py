"""
Automatic, controlled case-processing orchestration (Phase 22).
Master Specification Section 57 ("Forensic Workflow Orchestrator"),
Section 58 ("Processing Graph").

============================================================================
PHASE 22 GAP ASSESSMENT (recorded here per this phase's own instructions)
============================================================================
Before writing this module, the existing codebase (Phases 1-21) was
inspected for: a processing orchestrator, a case-processing workflow, a
job dependency model, a task scheduler/background worker, a findings
model, an alert/notification model, an activity feed, an event bus, a
case status machine, a processing policy, a frontend notification UI, and
any existing "run all" endpoint.

Found:
    - `app.models.job.Job` / `app.core.job_manager.JobManager` (Phase 13):
      a generic, synchronous job-persistence layer. Reused as-is; this
      phase adds only `Job.parent_job_id` for dependency tracking.
    - `app.models.case.CaseStatus` already declares `PROCESSING`/`REVIEW`
      states nothing previously transitioned a case through -- reused,
      not redefined.
    - `app.core.provenance_manager.ProvenanceManager` /
      `app.core.audit_chain_manager.AuditChainManager` (Phase 15/16): the
      append-only processing history and hash chain. Reused unchanged;
      this phase's own operations (`ORCHESTRATION`, `FINDING_GENERATION`)
      were added to `app.audit.events.ProcessingOperation`'s existing
      vocabulary, not a parallel log.
    - This backend has **no** background worker, task queue, event bus,
      websocket, or SSE mechanism anywhere (every Phase 9-18 manager's own
      docstring documents running synchronously to completion inside one
      call -- see e.g. `AIManager.run_job`'s docstring). This orchestrator
      follows the same, already-established pattern rather than
      introducing fake asynchrony.
    - `app.core.processing_orchestrator` (this file) and
      `app.core.capability_registry` existed only as empty (0-byte)
      placeholder files, present since the very first "architecture
      created" commit and never wired into `app.main` -- confirmed via
      `git log` -- i.e. genuinely unimplemented scaffolding, not a prior
      phase's abandoned work. `capability_registry` is not reintroduced:
      `app.adapters.base.AdapterCapability`/`app.adapters.registry.
      AdapterRegistry` (Phase 7/19) already is that concept, and remains
      the only one -- see `_evidence_has_supported_recordings` below for
      why this orchestrator still cannot dispatch through it (no vendor
      is wired into `AdapterRegistry` via real device identification
      yet, exactly as `RecordingManager`'s own module docstring documents).

    Not found anywhere: `Finding`, `Notification`, a dependency-graph
    model beyond `Job` itself, a scheduler, an event bus, a "run all case
    processing" endpoint. This phase adds exactly these
    (`app.models.finding.Finding`, `app.models.notification.
    Notification`, `Job.parent_job_id`, `ProcessingOrchestrator`/
    `FindingsEngine`/`NotificationManager`, and the new API routes) --
    nothing else.

============================================================================
WHAT THIS MODULE DOES AND DOES NOT DO
============================================================================
`ProcessingOrchestrator.process_case` is the one high-level entry point
(Master Specification Section 57's pseudo-flow, minus the acquisition/
adapter-selection/report/anchor steps this phase's boundary excludes):
for every evidence item in a case it runs integrity -> identification ->
enumeration -> extraction -> recovery -> timestamp normalization ->
timeline ingestion -> (optional) AI, then at the case level runs
correlation (only when >= 2 camera/event sources exist) and validation
(only when a ground-truth dataset already exists), then checks the audit
chain, then generates findings and notifications.

It never reimplements any of those steps -- every one is a direct call
into the existing Phase 6/9/10/11/12/13/14/15/16 manager that already
implements it. It never fabricates success: a step whose own manager
already reports partial/failed/unsupported is recorded as exactly that,
and `app.core.findings_engine.FindingsEngine` turns the honest result into
a hedged, traceable `Finding` -- never a stronger claim than the
underlying result supports (see that module's own docstring).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.acquisition.native_export import NATIVE_EXPORT_SOURCE_TYPE
from app.audit import ActorType, ProcessingOperation
from app.core.ai_manager import AIManager
from app.core.audit_chain_manager import AuditChainManager
from app.core.case_manager import CaseManager
from app.core.correlation_manager import CorrelationManager
from app.core.evidence_manager import EvidenceManager
from app.core.findings_engine import FindingsEngine
from app.core.job_manager import JobManager
from app.core.notification_manager import NotificationManager
from app.core.processing_policy import ProcessingPolicy
from app.core.provenance_manager import ProvenanceManager
from app.core.recording_manager import RecordingManager
from app.core.recovery_manager import RecoveryManager
from app.core.timeline_manager import TimelineManager
from app.core.timestamp_manager import TimestampManager
from app.core.validation_manager import ValidationManager
from app.integrity.hash_verification import IntegrityManager
from app.models import (
    ORCHESTRATION_JOB_TYPE,
    CaseStatus,
    Evidence,
    Finding,
    FindingConfidence,
    FindingSeverity,
    FindingType,
    GroundTruth,
    Job,
    JobStatus,
    Recording,
    RecordingMetadata,
    RecoveryResult,
    TimelineEvent,
    User,
    VerificationStatus,
)
from app.recovery import RecoveryStatus
from app.validation.benchmark import ValidationType

__all__ = ["ProcessingOrchestrator", "ProcessingRunSummary"]

#: Stage `Job.job_type` values this orchestrator writes for its
#: dependency-tracked children (task Phase 22 scope, "Job Dependency
#: Model"). Plain strings, not a closed enum -- see `app.models.job`'s
#: own "unknown values must be explicit, not fabricated" convention.
STAGE_INTEGRITY = "integrity"
STAGE_IDENTIFICATION = "identification"
STAGE_ENUMERATION = "enumeration"
STAGE_EXTRACTION = "extraction"
STAGE_RECOVERY = "recovery"
STAGE_TIMESTAMP_NORMALIZATION = "timestamp_normalization"
STAGE_TIMELINE = "timeline"
STAGE_AI = "ai"
STAGE_CORRELATION = "correlation"
STAGE_VALIDATION = "validation"

@dataclass
class ProcessingRunSummary:
    """Everything `POST /cases/{case_id}/process` needs to report back
    beyond the root `Job` itself."""

    root_job: Job
    new_finding_ids: list[int] = field(default_factory=list)
    notification_ids: list[int] = field(default_factory=list)


class ProcessingOrchestrator:
    """Coordinates the existing per-phase managers into one controlled,
    automatic, idempotent case-processing run."""

    # ------------------------------------------------------------------
    # Root entry point
    # ------------------------------------------------------------------

    @staticmethod
    def process_case(
        db: Session,
        case_id: int,
        *,
        policy: ProcessingPolicy | None = None,
        triggered_by: User | None = None,
    ) -> ProcessingRunSummary:
        """Run the full automatic case-processing workflow.

        Safe to call more than once (task Phase 22 scope, "Idempotency"):
        with `policy.force_reprocess=False` (the default), a stage that
        already produced a result for a given evidence/recording is left
        untouched and simply reported as already-complete; with
        `force_reprocess=True`, every applicable stage recomputes,
        producing new, independently-traceable result rows (Phase 9/10/11
        already append rather than overwrite).

        Args:
            db: Database session.
            case_id: The case to process. Must exist.
            policy: Which conditionally-automatic steps to run. Defaults
                to `ProcessingPolicy()` when omitted -- recorded verbatim
                on the root job's `parameters` either way.
            triggered_by: The authenticated officer who requested this
                run, if any. Only used to address notifications; a run
                with no `triggered_by` still generates and persists
                findings, it simply notifies nobody (there is no
                recipient to address).

        Returns:
            A `ProcessingRunSummary` wrapping the finished root `Job`.

        Raises:
            ValueError: If `case_id` does not exist.
        """
        active_policy = policy if policy is not None else ProcessingPolicy()

        case = CaseManager.get_case(db, case_id)
        if case is None:
            raise ValueError(f"Case with id {case_id} not found")

        root = JobManager.create_job(
            db, case_id=case_id, job_type=ORCHESTRATION_JOB_TYPE, parameters=active_policy.as_dict()
        )
        root = JobManager.mark_running(db, root)

        if case.status in (CaseStatus.DRAFT, CaseStatus.ACTIVE):
            case.status = CaseStatus.PROCESSING
            db.add(case)
            db.commit()

        warnings: list[str] = []
        stage_statuses: list[str] = []
        new_findings: list[Finding] = []

        evidence_rows = EvidenceManager.list_case_evidence(db, case_id, skip=0, limit=10_000)
        for evidence in evidence_rows:
            stage_statuses.extend(
                ProcessingOrchestrator._process_evidence(
                    db, evidence, active_policy, root, new_findings, warnings
                )
            )

        stage_statuses.append(
            ProcessingOrchestrator._run_correlation_stage(
                db, case_id, active_policy, root, new_findings, warnings
            )
        )
        stage_statuses.append(
            ProcessingOrchestrator._run_validation_stage(
                db, case_id, active_policy, root, new_findings, warnings
            )
        )
        ProcessingOrchestrator._check_audit_chain(db, case_id, root, new_findings)

        overall = _aggregate_status(stage_statuses)
        root = JobManager.finish_job(
            db,
            root,
            status=overall,
            results_count=len(new_findings),
            warnings=warnings or None,
        )

        if case.status == CaseStatus.PROCESSING:
            case.status = CaseStatus.REVIEW
            db.add(case)
            db.commit()

        ProvenanceManager.record_event(
            db,
            case_id=case_id,
            operation=ProcessingOperation.ORCHESTRATION.value,
            actor="ProcessingOrchestrator",
            actor_type=ActorType.SYSTEM,
            status=overall,
            job_id=root.id,
            parameters=active_policy.as_dict(),
            started_at=root.started_at,
            completed_at=root.completed_at,
            warnings=warnings or None,
            description=(
                f"Automatic case-processing run over {len(evidence_rows)} evidence item(s); "
                f"{len(new_findings)} finding(s) generated or updated."
            ),
        )

        notification_ids: list[int] = []
        if active_policy.notify and triggered_by is not None:
            for finding in new_findings:
                notification = NotificationManager.notify(
                    db, recipient_user_id=triggered_by.id, finding=finding
                )
                notification_ids.append(notification.id)

        return ProcessingRunSummary(
            root_job=root,
            new_finding_ids=[f.id for f in new_findings],
            notification_ids=notification_ids,
        )

    @staticmethod
    def get_processing_run(db: Session, root_job_id: int) -> Job | None:
        """Fetch a previously-run root orchestration job, including its
        dependency-tracked children (`Job.child_jobs`)."""
        return (
            db.query(Job)
            .filter(Job.id == root_job_id, Job.job_type == ORCHESTRATION_JOB_TYPE)
            .first()
        )

    @staticmethod
    def list_processing_runs(db: Session, case_id: int) -> list[Job]:
        """List every root orchestration run for a case, most recent first."""
        return (
            db.query(Job)
            .filter(Job.case_id == case_id, Job.job_type == ORCHESTRATION_JOB_TYPE)
            .order_by(Job.id.desc())
            .all()
        )

    # ------------------------------------------------------------------
    # Evidence-level pipeline
    # ------------------------------------------------------------------

    @staticmethod
    def _process_evidence(
        db: Session,
        evidence: Evidence,
        policy: ProcessingPolicy,
        root: Job,
        new_findings: list[Finding],
        run_warnings: list[str],
    ) -> list[str]:
        statuses: list[str] = []

        statuses.append(
            ProcessingOrchestrator._run_integrity_stage(db, evidence, root, new_findings)
        )
        statuses.append(ProcessingOrchestrator._run_identification_stage(db, evidence, root))

        recordings, enumeration_status = ProcessingOrchestrator._run_enumeration_stage(
            db, evidence, root, new_findings
        )
        statuses.append(enumeration_status)
        if not recordings:
            return statuses

        extraction_status, extracted_ok_ids = ProcessingOrchestrator._run_extraction_stage(
            db, evidence, recordings, policy, root, new_findings
        )
        statuses.append(extraction_status)

        statuses.append(
            ProcessingOrchestrator._run_recovery_stage(
                db, evidence, recordings, policy, root, new_findings
            )
        )
        statuses.append(
            ProcessingOrchestrator._run_timestamp_stage(
                db, evidence, recordings, policy, root, new_findings
            )
        )
        statuses.append(ProcessingOrchestrator._run_timeline_stage(db, evidence, recordings, root))

        if policy.run_ai:
            statuses.append(
                ProcessingOrchestrator._run_ai_stage(
                    db, evidence, extracted_ok_ids, policy, root, new_findings, run_warnings
                )
            )

        return statuses

    @staticmethod
    def _run_integrity_stage(
        db: Session, evidence: Evidence, root: Job, new_findings: list[Finding]
    ) -> str:
        job = ProcessingOrchestrator._start_stage(db, root, STAGE_INTEGRITY, evidence.id)
        if not evidence.source_path:
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.SKIPPED,
                warnings=["evidence has no source_path to hash"],
                operation=ProcessingOperation.IDENTIFICATION,
                evidence_id=evidence.id,
            )

        try:
            existing = IntegrityManager.list_evidence_hashes(db, evidence.id)
            hashes = (
                IntegrityManager.hash_evidence(db, evidence.id)
                if not existing
                else IntegrityManager.verify_evidence(db, evidence.id)
            )
        except (FileNotFoundError, ValueError) as exc:
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.FAILED,
                error=str(exc),
                operation=ProcessingOperation.IDENTIFICATION,
                evidence_id=evidence.id,
            )

        mismatches = [h for h in hashes if h.verification_status == VerificationStatus.MISMATCH]
        if mismatches:
            finding, is_new = FindingsEngine.upsert_finding(
                db,
                case_id=evidence.case_id,
                finding_type=FindingType.INTEGRITY_MISMATCH,
                severity=FindingSeverity.HIGH,
                confidence=FindingConfidence.VERIFIED,
                title=f"Integrity mismatch on evidence {evidence.evidence_id!r}",
                description=(
                    "The current representation of this evidence item differs from its "
                    "previously recorded representation: a recomputed hash does not match "
                    "the value stored at intake. This is an observation about the file's "
                    "current bytes, not a determination of cause, intent, or tampering -- "
                    "an examiner should independently investigate why the value changed."
                ),
                evidence_id=evidence.id,
                source_job_id=job.id,
                source_reference={"evidence_hash_ids": [h.id for h in mismatches]},
            )
            if is_new:
                new_findings.append(finding)

        return ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=JobStatus.FAILED if mismatches else JobStatus.COMPLETED,
            results_count=len(hashes),
            operation=ProcessingOperation.IDENTIFICATION,
            evidence_id=evidence.id,
        )

    @staticmethod
    def _run_identification_stage(db: Session, evidence: Evidence, root: Job) -> str:
        job = ProcessingOrchestrator._start_stage(db, root, STAGE_IDENTIFICATION, evidence.id)
        if not evidence.source_path:
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.SKIPPED,
                warnings=["evidence has no source_path to identify"],
                operation=ProcessingOperation.IDENTIFICATION,
                evidence_id=evidence.id,
            )
        try:
            EvidenceManager.identify_device(db, evidence.id)
            EvidenceManager.detect_format(db, evidence.id)
        except ValueError as exc:
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.FAILED,
                error=str(exc),
                operation=ProcessingOperation.IDENTIFICATION,
                evidence_id=evidence.id,
            )
        return ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=JobStatus.COMPLETED,
            operation=ProcessingOperation.IDENTIFICATION,
            evidence_id=evidence.id,
        )

    @staticmethod
    def _run_enumeration_stage(
        db: Session, evidence: Evidence, root: Job, new_findings: list[Finding]
    ) -> tuple[list[Recording], str]:
        job = ProcessingOrchestrator._start_stage(db, root, STAGE_ENUMERATION, evidence.id)
        if not evidence.source_path:
            status = ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.SKIPPED,
                warnings=["evidence has no source_path to enumerate"],
                operation=ProcessingOperation.PARSING,
                evidence_id=evidence.id,
            )
            return [], status

        try:
            recordings = RecordingManager.enumerate_recordings(db, evidence.id)
        except ValueError as exc:
            status = ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.FAILED,
                error=str(exc),
                operation=ProcessingOperation.PARSING,
                evidence_id=evidence.id,
            )
            return [], status

        if not recordings:
            # `RecordingManager.enumerate_recordings`'s own documented
            # contract: an empty result is a clean, honest "this evidence
            # does not match a supported structure" -- never an error.
            # Only worth an examiner's attention when the evidence was
            # actually declared as a structured native export (task Phase
            # 22 scope, "Vendor Automation": a Level 1-only vendor must
            # not be silently treated as fully processed).
            if evidence.source_type == NATIVE_EXPORT_SOURCE_TYPE:
                finding, is_new = FindingsEngine.upsert_finding(
                    db,
                    case_id=evidence.case_id,
                    finding_type=FindingType.UNSUPPORTED_FORMAT,
                    severity=FindingSeverity.MEDIUM,
                    confidence=FindingConfidence.NOT_APPLICABLE,
                    title=f"No recordings enumerated for evidence {evidence.evidence_id!r}",
                    description=(
                        "This evidence item was registered as a native DVR/NVR export, but no "
                        "recordings could be enumerated from it. This backend currently "
                        "validates structured recording enumeration for CP Plus evidence only "
                        "(Master Specification Section 17/Phase 19 support matrix); other "
                        "vendors or an unrecognized structure return no recordings rather than "
                        "a fabricated result. Further extraction/recovery requires examiner "
                        "review of this evidence's actual format."
                    ),
                    evidence_id=evidence.id,
                    source_job_id=job.id,
                )
                if is_new:
                    new_findings.append(finding)
            status = ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.SKIPPED,
                results_count=0,
                operation=ProcessingOperation.PARSING,
                evidence_id=evidence.id,
            )
            return [], status

        status = ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=JobStatus.COMPLETED,
            results_count=len(recordings),
            operation=ProcessingOperation.PARSING,
            evidence_id=evidence.id,
        )
        return recordings, status

    @staticmethod
    def _run_extraction_stage(
        db: Session,
        evidence: Evidence,
        recordings: list[Recording],
        policy: ProcessingPolicy,
        root: Job,
        new_findings: list[Finding],
    ) -> tuple[str, list[int]]:
        job = ProcessingOrchestrator._start_stage(
            db, root, STAGE_EXTRACTION, evidence.id, recording_ids=[r.id for r in recordings]
        )
        if not policy.run_extraction:
            status = ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.REQUIRES_REVIEW,
                warnings=["extraction disabled by processing policy"],
                operation=ProcessingOperation.EXTRACTION,
                evidence_id=evidence.id,
            )
            return status, []

        succeeded: list[int] = []
        partial = False
        failed = False
        stage_warnings: list[str] = []
        for recording in recordings:
            existing_status = ProcessingOrchestrator._recording_metadata_value(
                db, recording.id, "extraction_status"
            )
            if existing_status is not None and not policy.force_reprocess:
                if existing_status == "successful":
                    succeeded.append(recording.id)
                elif existing_status == "partial":
                    partial = True
                    succeeded.append(recording.id)
                else:
                    failed = True
                continue

            try:
                updated = RecordingManager.extract_recording(db, recording.id)
            except ValueError as exc:
                failed = True
                stage_warnings.append(f"recording {recording.recording_id!r}: {exc}")
                continue
            outcome = ProcessingOrchestrator._recording_metadata_value(
                db, updated.id, "extraction_status"
            )
            if outcome == "successful":
                succeeded.append(updated.id)
            elif outcome == "partial":
                partial = True
                succeeded.append(updated.id)
                ProcessingOrchestrator._corrupted_recording_finding(
                    db, evidence, updated, job, new_findings, severity=FindingSeverity.MEDIUM
                )
            else:
                failed = True
                ProcessingOrchestrator._corrupted_recording_finding(
                    db, evidence, updated, job, new_findings, severity=FindingSeverity.HIGH
                )

        if succeeded and not failed and not partial:
            final_status = JobStatus.COMPLETED
        elif succeeded:
            final_status = JobStatus.PARTIAL
        else:
            final_status = JobStatus.FAILED

        status = ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=final_status,
            warnings=stage_warnings or None,
            results_count=len(succeeded),
            operation=ProcessingOperation.EXTRACTION,
            evidence_id=evidence.id,
        )
        return status, succeeded

    @staticmethod
    def _corrupted_recording_finding(
        db: Session,
        evidence: Evidence,
        recording: Recording,
        job: Job,
        new_findings: list[Finding],
        *,
        severity: FindingSeverity,
    ) -> None:
        warnings_raw = ProcessingOrchestrator._recording_metadata_value(
            db, recording.id, "extraction_warnings"
        )
        warnings = json.loads(warnings_raw) if warnings_raw else []
        finding, is_new = FindingsEngine.upsert_finding(
            db,
            case_id=evidence.case_id,
            finding_type=FindingType.CORRUPTED_RECORDING,
            severity=severity,
            confidence=FindingConfidence.VERIFIED,
            title=f"Extraction issue on recording {recording.recording_id!r}",
            description=(
                "Extracting this recording's media stream encountered truncation or "
                "corruption in the source data. Frames recoverable up to that point were "
                "extracted; anything past it was not. This describes a data-integrity "
                "condition in the source, not a conclusion about who or what caused it."
            ),
            evidence_id=evidence.id,
            recording_id=recording.id,
            source_job_id=job.id,
            source_reference={"recording_id": recording.id},
            limitations=warnings[:10] if warnings else None,
        )
        if is_new:
            new_findings.append(finding)

    @staticmethod
    def _run_recovery_stage(
        db: Session,
        evidence: Evidence,
        recordings: list[Recording],
        policy: ProcessingPolicy,
        root: Job,
        new_findings: list[Finding],
    ) -> str:
        job = ProcessingOrchestrator._start_stage(
            db, root, STAGE_RECOVERY, evidence.id, recording_ids=[r.id for r in recordings]
        )
        if not policy.run_recovery:
            for recording in recordings:
                finding, is_new = FindingsEngine.upsert_finding(
                    db,
                    case_id=evidence.case_id,
                    finding_type=FindingType.RECOVERY_AVAILABLE_FOR_REVIEW,
                    severity=FindingSeverity.INFO,
                    confidence=FindingConfidence.NOT_APPLICABLE,
                    title=f"Recovery available for review on recording {recording.recording_id!r}",
                    description=(
                        "Layered recovery has not been run automatically for this recording "
                        "per the current processing policy. An examiner can run it explicitly "
                        "via the recovery API."
                    ),
                    evidence_id=evidence.id,
                    recording_id=recording.id,
                    source_job_id=job.id,
                )
                if is_new:
                    new_findings.append(finding)
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.REQUIRES_REVIEW,
                operation=ProcessingOperation.RECOVERY,
                evidence_id=evidence.id,
            )

        any_partial = False
        any_failed = False
        attempted = 0
        stage_warnings: list[str] = []
        for recording in recordings:
            existing = (
                db.query(RecoveryResult).filter(RecoveryResult.recording_id == recording.id).count()
            )
            if existing and not policy.force_reprocess:
                continue
            attempted += 1
            try:
                result = RecoveryManager.run_recovery(db, recording.id)
            except ValueError as exc:
                any_failed = True
                stage_warnings.append(f"recording {recording.recording_id!r}: {exc}")
                continue
            if result.status == RecoveryStatus.PARTIAL.value:
                any_partial = True
                finding, is_new = FindingsEngine.upsert_finding(
                    db,
                    case_id=evidence.case_id,
                    finding_type=FindingType.PARTIAL_RECOVERY,
                    severity=FindingSeverity.MEDIUM,
                    confidence=FindingConfidence.VERIFIED,
                    title=f"Partial recovery on recording {recording.recording_id!r}",
                    description=(
                        f"Layered recovery (method={result.method!r}) recovered some but not "
                        "all of this recording's data. This is a partial result, not a "
                        "complete reconstruction -- treat any gap as unresolved, not as "
                        "evidence of what the missing portion contained."
                    ),
                    evidence_id=evidence.id,
                    recording_id=recording.id,
                    source_job_id=job.id,
                    source_reference={"recovery_result_id": result.id},
                )
                if is_new:
                    new_findings.append(finding)
            elif result.status == RecoveryStatus.FAILED.value:
                any_failed = True
            elif result.status == RecoveryStatus.RECOVERED.value and (
                (result.confidence is not None and result.confidence < 0.5)
                or (result.frame_continuity is not None and result.frame_continuity < 1.0)
            ):
                finding, is_new = FindingsEngine.upsert_finding(
                    db,
                    case_id=evidence.case_id,
                    finding_type=FindingType.RECOVERY_WARNING,
                    severity=FindingSeverity.LOW,
                    confidence=FindingConfidence.PARTIAL,
                    title=f"Recovery confidence/continuity caveat on recording {recording.recording_id!r}",
                    description=(
                        "This recording was recovered, but the recovery engine reports "
                        "reduced confidence or incomplete frame continuity. Review the "
                        "recovered artifact before relying on it as a complete record."
                    ),
                    evidence_id=evidence.id,
                    recording_id=recording.id,
                    source_job_id=job.id,
                    source_reference={"recovery_result_id": result.id},
                )
                if is_new:
                    new_findings.append(finding)

        if attempted == 0:
            final_status = JobStatus.SKIPPED
        elif any_failed and not any_partial:
            final_status = JobStatus.FAILED
        elif any_failed or any_partial:
            final_status = JobStatus.PARTIAL
        else:
            final_status = JobStatus.COMPLETED

        return ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=final_status,
            results_count=attempted,
            warnings=stage_warnings or None,
            operation=ProcessingOperation.RECOVERY,
            evidence_id=evidence.id,
        )

    @staticmethod
    def _run_timestamp_stage(
        db: Session,
        evidence: Evidence,
        recordings: list[Recording],
        policy: ProcessingPolicy,
        root: Job,
        new_findings: list[Finding],
    ) -> str:
        job = ProcessingOrchestrator._start_stage(
            db, root, STAGE_TIMESTAMP_NORMALIZATION, evidence.id, recording_ids=[r.id for r in recordings]
        )
        if not policy.run_timestamp_normalization:
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.SKIPPED,
                warnings=["timestamp normalization disabled by processing policy"],
                operation=ProcessingOperation.TIMESTAMP_NORMALIZATION,
                evidence_id=evidence.id,
            )

        for recording in recordings:
            TimestampManager.normalize_recording(db, recording.id)
            db.refresh(recording)
            if (
                recording.start_original is not None
                and recording.end_original is not None
                and recording.end_original < recording.start_original
            ):
                finding, is_new = FindingsEngine.upsert_finding(
                    db,
                    case_id=evidence.case_id,
                    finding_type=FindingType.TIMESTAMP_INCONSISTENCY,
                    severity=FindingSeverity.HIGH,
                    confidence=FindingConfidence.VERIFIED,
                    title=f"Timestamp ordering inconsistency on recording {recording.recording_id!r}",
                    description=(
                        "This recording's recorded end timestamp precedes its start "
                        "timestamp. This is an observed inconsistency in the source "
                        "timestamps, not a determination of falsification -- clock errors, "
                        "vendor encoding quirks, or an unresolved timezone are all possible "
                        "explanations an examiner should investigate."
                    ),
                    evidence_id=evidence.id,
                    recording_id=recording.id,
                    source_job_id=job.id,
                )
                if is_new:
                    new_findings.append(finding)

        return ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=JobStatus.COMPLETED,
            results_count=len(recordings),
            operation=ProcessingOperation.TIMESTAMP_NORMALIZATION,
            evidence_id=evidence.id,
        )

    @staticmethod
    def _run_timeline_stage(
        db: Session, evidence: Evidence, recordings: list[Recording], root: Job
    ) -> str:
        job = ProcessingOrchestrator._start_stage(
            db, root, STAGE_TIMELINE, evidence.id, recording_ids=[r.id for r in recordings]
        )
        for recording in recordings:
            TimelineManager.ingest_recording_events(db, recording.id)
        return ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=JobStatus.COMPLETED,
            results_count=len(recordings) * 2,
            operation=ProcessingOperation.TIMELINE,
            evidence_id=evidence.id,
        )

    @staticmethod
    def _run_ai_stage(
        db: Session,
        evidence: Evidence,
        extracted_recording_ids: list[int],
        policy: ProcessingPolicy,
        root: Job,
        new_findings: list[Finding],
        run_warnings: list[str],
    ) -> str:
        job = ProcessingOrchestrator._start_stage(
            db, root, STAGE_AI, evidence.id, recording_ids=extracted_recording_ids
        )
        if not extracted_recording_ids:
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.BLOCKED,
                warnings=["no successfully-extracted recording available for AI analysis"],
                operation=ProcessingOperation.AI_ANALYSIS,
                evidence_id=evidence.id,
            )

        ai_job = AIManager.run_job(
            db,
            case_id=evidence.case_id,
            recording_ids=extracted_recording_ids,
            analysis_types=list(policy.ai_analysis_types),
        )
        if ai_job.status == JobStatus.FAILED.value:
            run_warnings.append(f"AI analysis unavailable for evidence {evidence.evidence_id!r}: {ai_job.error}")
            finding, is_new = FindingsEngine.upsert_finding(
                db,
                case_id=evidence.case_id,
                finding_type=FindingType.PROCESSING_FAILURE,
                severity=FindingSeverity.LOW,
                confidence=FindingConfidence.NOT_APPLICABLE,
                title=f"AI analysis unavailable for evidence {evidence.evidence_id!r}",
                description=(
                    f"Automatic AI analysis could not run: {ai_job.error}. Other processing "
                    "results for this evidence are unaffected."
                ),
                evidence_id=evidence.id,
                source_job_id=ai_job.id,
            )
            if is_new:
                new_findings.append(finding)
        elif ai_job.results_count > 0:
            finding, is_new = FindingsEngine.upsert_finding(
                db,
                case_id=evidence.case_id,
                finding_type=FindingType.AI_DETECTION,
                severity=FindingSeverity.INFO,
                confidence=FindingConfidence.UNVERIFIED,
                title=f"AI analysis produced {ai_job.results_count} result(s) for evidence {evidence.evidence_id!r}",
                description=(
                    f"Automatic AI analysis ({', '.join(policy.ai_analysis_types)}) produced "
                    f"{ai_job.results_count} detection/track/motion result(s). These are "
                    "algorithmic detections only -- not identity, not proof of guilt, and not "
                    "independently verified. Review the underlying results before drawing any "
                    "conclusion."
                ),
                evidence_id=evidence.id,
                source_job_id=ai_job.id,
                source_reference={"ai_job_id": ai_job.id},
            )
            if is_new:
                new_findings.append(finding)

        status_map = {
            JobStatus.COMPLETED.value: JobStatus.COMPLETED,
            JobStatus.PARTIAL.value: JobStatus.PARTIAL,
            JobStatus.FAILED.value: JobStatus.FAILED,
        }
        return ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=status_map.get(ai_job.status, JobStatus.PARTIAL),
            results_count=ai_job.results_count,
            operation=ProcessingOperation.AI_ANALYSIS,
            evidence_id=evidence.id,
        )

    # ------------------------------------------------------------------
    # Case-level pipeline
    # ------------------------------------------------------------------

    @staticmethod
    def _run_correlation_stage(
        db: Session,
        case_id: int,
        policy: ProcessingPolicy,
        root: Job,
        new_findings: list[Finding],
        run_warnings: list[str],
    ) -> str:
        job = ProcessingOrchestrator._start_stage(db, root, STAGE_CORRELATION, evidence_id=None)
        if not policy.run_correlation:
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.SKIPPED,
                warnings=["correlation disabled by processing policy"],
                operation=ProcessingOperation.CORRELATION,
            )

        camera_sources = (
            db.query(TimelineEvent.camera_id)
            .filter(TimelineEvent.case_id == case_id, TimelineEvent.camera_id.isnot(None))
            .distinct()
            .count()
        )
        if camera_sources < 2:
            run_warnings.append(
                f"cross-camera correlation not applicable: only {camera_sources} camera/event "
                "source(s) in this case"
            )
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.SKIPPED,
                operation=ProcessingOperation.CORRELATION,
            )

        _result, persisted = CorrelationManager.run_correlation(db, case_id)
        if persisted:
            finding, is_new = FindingsEngine.upsert_finding(
                db,
                case_id=case_id,
                finding_type=FindingType.CROSS_CAMERA_CORRELATION,
                severity=FindingSeverity.INFO,
                confidence=FindingConfidence.UNVERIFIED,
                title=f"{len(persisted)} cross-camera correlation candidate(s) found",
                description=(
                    "Automatic correlation found timeline events across cameras close enough "
                    "in time to be temporally related. A correlation candidate links events "
                    "in time only -- it does not establish that the same person or vehicle is "
                    "involved, and it is not proof of any sequence of events."
                ),
                source_job_id=job.id,
                source_reference={"correlated_event_ids": [e.id for e in persisted]},
            )
            if is_new:
                new_findings.append(finding)

        return ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=JobStatus.COMPLETED,
            results_count=len(persisted),
            operation=ProcessingOperation.CORRELATION,
        )

    @staticmethod
    def _run_validation_stage(
        db: Session,
        case_id: int,
        policy: ProcessingPolicy,
        root: Job,
        new_findings: list[Finding],
        run_warnings: list[str],
    ) -> str:
        job = ProcessingOrchestrator._start_stage(db, root, STAGE_VALIDATION, evidence_id=None)
        if not policy.run_validation:
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.SKIPPED,
                warnings=["validation disabled by processing policy"],
                operation=ProcessingOperation.VALIDATION,
            )

        dataset_pairs = (
            db.query(GroundTruth.dataset_id, GroundTruth.event_type)
            .filter(GroundTruth.case_id == case_id)
            .distinct()
            .all()
        )
        if not dataset_pairs:
            finding, is_new = FindingsEngine.upsert_finding(
                db,
                case_id=case_id,
                finding_type=FindingType.VALIDATION_NOT_RUN,
                severity=FindingSeverity.INFO,
                confidence=FindingConfidence.NOT_APPLICABLE,
                title="Validation could not be completed: no ground-truth dataset configured",
                description=(
                    "No ground-truth dataset is configured for this case, so automatic "
                    "processing did not run validation. This is not a negative result about "
                    "the case's evidence -- it means no metric has been computed either way. "
                    "An examiner can configure a ground-truth dataset and run validation "
                    "explicitly."
                ),
                source_job_id=job.id,
            )
            if is_new:
                new_findings.append(finding)
            return ProcessingOrchestrator._finish_stage(
                db,
                job,
                root,
                status=JobStatus.REQUIRES_REVIEW,
                operation=ProcessingOperation.VALIDATION,
            )

        any_partial = False
        any_failed = False
        total_metrics = 0
        for dataset_id, event_type in dataset_pairs:
            if event_type not in {vt.value for vt in ValidationType}:
                continue
            val_job, metrics = ValidationManager.run_validation(
                db, case_id=case_id, validation_type=event_type, dataset_id=dataset_id
            )
            total_metrics += len(metrics)
            if val_job.status == JobStatus.FAILED.value:
                any_failed = True
            elif val_job.status == JobStatus.PARTIAL.value:
                any_partial = True
                finding, is_new = FindingsEngine.upsert_finding(
                    db,
                    case_id=case_id,
                    finding_type=FindingType.VALIDATION_FAILURE,
                    severity=FindingSeverity.MEDIUM,
                    confidence=FindingConfidence.PARTIAL,
                    title=f"Validation warnings for dataset {dataset_id!r} ({event_type})",
                    description=(
                        f"Validation against ground-truth dataset {dataset_id!r} "
                        f"({event_type}) completed with warnings -- one or more comparisons "
                        "could not be fully resolved. Review the underlying validation "
                        "metrics before treating this validation run as conclusive."
                    ),
                    source_job_id=val_job.id,
                    source_reference={"validation_job_id": val_job.id, "dataset_id": dataset_id},
                )
                if is_new:
                    new_findings.append(finding)

        if any_failed:
            final_status = JobStatus.FAILED
        elif any_partial:
            final_status = JobStatus.PARTIAL
        else:
            final_status = JobStatus.COMPLETED

        return ProcessingOrchestrator._finish_stage(
            db,
            job,
            root,
            status=final_status,
            results_count=total_metrics,
            operation=ProcessingOperation.VALIDATION,
        )

    @staticmethod
    def _check_audit_chain(
        db: Session, case_id: int, root: Job, new_findings: list[Finding]
    ) -> None:
        result = AuditChainManager.verify_case_chain(db, case_id)
        if result.valid:
            return
        failure = result.failure
        finding, is_new = FindingsEngine.upsert_finding(
            db,
            case_id=case_id,
            finding_type=FindingType.AUDIT_CHAIN_INVALID,
            severity=FindingSeverity.CRITICAL,
            confidence=FindingConfidence.VERIFIED,
            title="Hash-linked audit chain is invalid",
            description=(
                "This case's hash-linked processing audit chain does not currently verify "
                f"(first failure at event {failure.event_id if failure else '?'}: "
                f"{failure.reason.value if failure else 'unknown'}). This indicates the "
                "recorded processing history itself needs urgent examiner/administrator "
                "investigation -- it is not, by itself, a statement about the evidence's "
                "content."
            ),
            source_job_id=root.id,
        )
        if is_new:
            new_findings.append(finding)

    # ------------------------------------------------------------------
    # Small shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _start_stage(
        db: Session,
        root: Job,
        stage: str,
        evidence_id: int | None,
        *,
        recording_ids: list[int] | None = None,
    ) -> Job:
        job = JobManager.create_job(
            db,
            case_id=root.case_id,
            job_type=stage,
            evidence_id=evidence_id,
            recording_ids=recording_ids,
        )
        job.parent_job_id = root.id
        db.add(job)
        db.commit()
        db.refresh(job)
        return JobManager.mark_running(db, job)

    @staticmethod
    def _finish_stage(
        db: Session,
        job: Job,
        root: Job,
        *,
        status: JobStatus,
        operation: ProcessingOperation,
        evidence_id: int | None = None,
        results_count: int | None = None,
        warnings: list[str] | None = None,
        error: str | None = None,
    ) -> str:
        job = JobManager.finish_job(
            db, job, status=status, results_count=results_count, warnings=warnings, error=error
        )
        ProvenanceManager.record_event(
            db,
            case_id=root.case_id,
            operation=operation.value,
            actor="ProcessingOrchestrator",
            actor_type=ActorType.SYSTEM,
            status=status,
            evidence_id=evidence_id,
            job_id=job.id,
            started_at=job.started_at,
            completed_at=job.completed_at,
            warnings=warnings,
            error=error,
        )
        return status.value

    @staticmethod
    def _recording_metadata_value(db: Session, recording_id: int, key: str) -> str | None:
        row = (
            db.query(RecordingMetadata)
            .filter(RecordingMetadata.recording_id == recording_id, RecordingMetadata.key == key)
            .first()
        )
        return row.value if row is not None else None


def _aggregate_status(stage_statuses: list[str]) -> JobStatus:
    """Deterministic root-job status from every stage's terminal status
    (task Phase 22 scope, "Failure Isolation": one failed optional
    operation must not necessarily fail the whole case).

    Rule: ignore `SKIPPED` stages entirely (not applicable is not a
    problem); if nothing meaningful remains, the run is itself `SKIPPED`;
    if every meaningful stage completed cleanly, the run is `COMPLETED`;
    if every meaningful stage failed outright, the run is `FAILED`; any
    other mix (some failed, some blocked/requires-review, some
    completed) is honestly reported as `PARTIAL` -- never silently
    rounded up to `COMPLETED`.
    """
    meaningful = [s for s in stage_statuses if s != JobStatus.SKIPPED.value]
    if not meaningful:
        return JobStatus.SKIPPED
    if all(s == JobStatus.COMPLETED.value for s in meaningful):
        return JobStatus.COMPLETED
    if all(s == JobStatus.FAILED.value for s in meaningful):
        return JobStatus.FAILED
    return JobStatus.PARTIAL
