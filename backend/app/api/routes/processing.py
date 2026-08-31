"""
API routes for automatic case-processing orchestration (Phase 22, revised
Phase 24-2: "Processing Performance, Accuracy/Validation, and Output
Parameter tables from REAL runtime data").

`POST /cases/{case_id}/process` is the one high-level "process this case"
operation task Phase 22 scope's own "Automatic Processing Trigger" section
asks for -- the officer never has to call a dozen separate phase APIs to
kick off automatic processing, while every one of those detailed APIs
(recovery, AI, validation, ...) remains directly callable for examiner
control, unchanged by this phase.

Requires authentication (task Phase 22 scope, "Authentication/
Authorization": findings/notifications must be attributable to the
requesting officer) -- unlike most Phase 1-20 routes, which predate Phase
21's `User`/session system entirely.

Three separate GET endpoints under `/processing/{root_job_id}/...`, never
merged into one response (task: "Do not mix performance and accuracy into
one metric"):
    - (no suffix): timing + resource usage (`ProcessingStageResponse`).
    - `/accuracy`: quality/validation signals, each with an explicit
      `AccuracyStatus` and its basis -- precision/recall/F1 only where a
      real `ValidationMetric`/`GroundTruth` pair exists, confidence always
      labeled as confidence, never as accuracy.
    - `/outputs`: what was actually produced (vendor/model, recording/
      detection/track counts, codec/resolution, recovery status, audit
      chain and blockchain-anchor state, artifact hashes, report format).
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_case_access
from app.api.routes.jobs import _job_response
from app.core.audit_chain_manager import AuditChainManager
from app.core.case_authorization_service import CaseAccessDeniedError, CaseAuthorizationService
from app.core.processing_orchestrator import (
    STAGE_AI,
    STAGE_CORRELATION,
    STAGE_ENUMERATION,
    STAGE_EXTRACTION,
    STAGE_IDENTIFICATION,
    STAGE_INTEGRITY,
    STAGE_RECOVERY,
    STAGE_TIMELINE,
    STAGE_TIMESTAMP_NORMALIZATION,
    STAGE_VALIDATION,
    ProcessingOrchestrator,
)
from app.core.processing_policy import ProcessingPolicy
from app.models import (
    AIResult,
    AITrack,
    BlockchainAnchor,
    Case,
    Device,
    EvidenceHash,
    Job,
    JobStatus,
    Recording,
    RecordingMetadata,
    RecoveryResult,
    Report,
    User,
    ValidationMetric,
)
from app.schemas.processing import (
    AccuracyMetricResponse,
    AccuracyStatus,
    AccuracyValidationResponse,
    OutputParameterResponse,
    OutputParametersResponse,
    ProcessingPolicyRequest,
    ProcessingRunRequest,
    ProcessingRunResponse,
    ProcessingStageResponse,
)
from app.storage.db import get_db

router = APIRouter()

#: Human-readable module titles for all three tables, keyed by the same
#: plain `job_type` strings `ProcessingOrchestrator` writes (see that
#: module's own "unknown values must be explicit, not fabricated"
#: convention -- any `job_type` not listed here falls back to a
#: title-cased rendering of the raw value rather than raising).
_STAGE_TITLES = {
    STAGE_INTEGRITY: "Integrity verification",
    STAGE_IDENTIFICATION: "Identification",
    STAGE_ENUMERATION: "Enumeration",
    STAGE_EXTRACTION: "Extraction",
    STAGE_RECOVERY: "Recovery",
    STAGE_TIMESTAMP_NORMALIZATION: "Timestamp normalization",
    STAGE_TIMELINE: "Timeline",
    STAGE_AI: "AI",
    STAGE_CORRELATION: "Correlation",
    STAGE_VALIDATION: "Validation",
}

#: `results_count`'s meaning for stages whose only real output is "how
#: many of X" -- reusing the count `ProcessingOrchestrator` already
#: computed rather than re-querying the same data a second time.
_RESULT_LABELS = {
    STAGE_ENUMERATION: "Recordings found",
    STAGE_EXTRACTION: "Recordings extracted",
    STAGE_TIMELINE: "Timeline events ingested",
    STAGE_CORRELATION: "Cross-camera correlation candidates",
}

_STAGE_STATUS_COUNT_FIELDS = {
    JobStatus.COMPLETED.value: "stages_completed",
    JobStatus.FAILED.value: "stages_failed",
    JobStatus.SKIPPED.value: "stages_skipped",
    JobStatus.BLOCKED.value: "stages_blocked",
    JobStatus.REQUIRES_REVIEW.value: "stages_requires_review",
}

#: `app.timeline.NormalizationStatus` value -> (`AccuracyStatus`, basis).
#: `VERIFIED` means an independently-sourced reference established the
#: true clock offset; `PARTIAL` means only one side (start/end) resolved
#: that far; `UNVERIFIED` means a timezone is known but nothing
#: independent corroborates it; `UNKNOWN` means nothing was resolvable.
_TIMESTAMP_STATUS_ACCURACY = {
    "verified": (AccuracyStatus.VALIDATED, "independently-sourced reference offset verified"),
    "partial": (AccuracyStatus.OBSERVATION, "only part of the recording's timestamps resolved"),
    "unverified": (
        AccuracyStatus.UNVERIFIED,
        "examiner-supplied timezone with no independent reference to verify against",
    ),
    "unknown": (AccuracyStatus.NOT_APPLICABLE, "no usable original timestamp or timezone"),
}


def _policy_from_request(request: ProcessingPolicyRequest | None) -> ProcessingPolicy:
    if request is None:
        return ProcessingPolicy()
    data = request.model_dump()
    if data.get("ai_analysis_types") is None:
        data.pop("ai_analysis_types")
    else:
        data["ai_analysis_types"] = tuple(data["ai_analysis_types"])
    return ProcessingPolicy(**data)


def _wall_clock_duration_seconds(
    started_at: datetime | None, completed_at: datetime | None
) -> float | None:
    """`completed_at - started_at` in seconds -- the coarse fallback used
    only when no high-resolution `resource_metrics` measurement exists on
    a job row."""
    if started_at is None or completed_at is None:
        return None
    return (completed_at - started_at).total_seconds()


def _stage_response(job: Job) -> ProcessingStageResponse:
    metrics = json.loads(job.resource_metrics) if job.resource_metrics else None
    has_high_res = bool(metrics and "runtime_seconds" in metrics)

    duration_seconds: float | None
    high_resolution_timing: bool | None
    if has_high_res:
        duration_seconds = metrics["runtime_seconds"]
        high_resolution_timing = True
    else:
        duration_seconds = _wall_clock_duration_seconds(job.started_at, job.completed_at)
        high_resolution_timing = False if duration_seconds is not None else None

    return ProcessingStageResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        evidence_id=job.evidence_id,
        recording_ids=json.loads(job.recording_ids) if job.recording_ids else None,
        progress=job.progress,
        results_count=job.results_count,
        error=job.error,
        warnings=json.loads(job.warnings) if job.warnings else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        duration_seconds=duration_seconds,
        high_resolution_timing=high_resolution_timing,
        cpu_user_seconds=metrics.get("cpu_user_seconds") if metrics else None,
        cpu_system_seconds=metrics.get("cpu_system_seconds") if metrics else None,
        peak_rss_kb=metrics.get("peak_rss_kb") if metrics else None,
        rss_delta_kb=metrics.get("rss_delta_kb") if metrics else None,
        input_type=metrics.get("input_type") if metrics else None,
        input_size=metrics.get("input_size") if metrics else None,
        input_size_unit=metrics.get("input_size_unit") if metrics else None,
    )


def _run_response(
    root_job: Job,
    *,
    new_finding_ids: list[int] | None = None,
    notification_ids: list[int] | None = None,
) -> ProcessingRunResponse:
    stages = [_stage_response(child) for child in sorted(root_job.child_jobs, key=lambda j: j.id)]
    counts = {field: 0 for field in _STAGE_STATUS_COUNT_FIELDS.values()}
    for stage in stages:
        field_name = _STAGE_STATUS_COUNT_FIELDS.get(stage.status)
        if field_name is not None:
            counts[field_name] += 1
    stage_durations = [s.duration_seconds for s in stages if s.duration_seconds is not None]
    return ProcessingRunResponse(
        root_job=_job_response(root_job),
        stages=stages,
        stages_total=len(stages),
        new_finding_ids=new_finding_ids or [],
        notification_ids=notification_ids or [],
        total_duration_seconds=sum(stage_durations) if stage_durations else None,
        **counts,
    )


_NON_OUTPUT_STATUSES = {
    JobStatus.SKIPPED.value,
    JobStatus.BLOCKED.value,
    JobStatus.REQUIRES_REVIEW.value,
    JobStatus.PENDING.value,
}


def _accuracy_metrics_for_stage(db: Session, job: Job) -> list[AccuracyMetricResponse]:
    """Real quality/validation signals for one pipeline-stage job.

    Never a single universal accuracy percentage, never a fabricated
    status: every row's `AccuracyStatus` follows the closed, documented
    mapping below from an actual persisted result -- precision/recall/F1
    only ever appear for the validation stage, and only when a real
    `ValidationMetric` row (backed by a real `GroundTruth` dataset)
    exists. Stages that only ever produce a count (enumeration,
    extraction, timeline) have no accuracy claim to make and are
    deliberately omitted here -- their counts belong in
    `_output_parameters_for_stage` instead."""
    module = _STAGE_TITLES.get(job.job_type, job.job_type.replace("_", " ").title())
    rows: list[AccuracyMetricResponse] = []

    def add(
        metric: str,
        value: object,
        accuracy_status: AccuracyStatus,
        basis: str,
        *,
        notes: str | None = None,
    ) -> None:
        rows.append(
            AccuracyMetricResponse(
                module=module,
                metric=metric,
                value=str(value),
                status=accuracy_status,
                basis=basis,
                source=f"job #{job.id}",
                notes=notes,
            )
        )

    if job.status in _NON_OUTPUT_STATUSES:
        return rows

    if job.job_type == STAGE_INTEGRITY and job.evidence_id is not None:
        hashes = db.query(EvidenceHash).filter(EvidenceHash.evidence_id == job.evidence_id).all()
        for h in hashes:
            if h.verification_status.value == "not_verified":
                add(
                    f"{h.algorithm.value.upper()} verification",
                    h.verification_status.value,
                    AccuracyStatus.NOT_APPLICABLE,
                    "hash computed at intake; no later recomputation to compare against yet",
                )
            else:
                add(
                    f"{h.algorithm.value.upper()} verification",
                    h.verification_status.value,
                    AccuracyStatus.VALIDATED,
                    "recomputed hash compared byte-for-byte against the value recorded at intake",
                )

    elif job.job_type == STAGE_IDENTIFICATION and job.evidence_id is not None:
        device = db.query(Device).filter(Device.evidence_id == job.evidence_id).first()
        if device is not None and device.vendor is not None:
            deterministic = device.identification_method == "cp_plus_structure_signature"
            add(
                "Vendor identification",
                device.vendor,
                AccuracyStatus.VALIDATED if deterministic else AccuracyStatus.UNVERIFIED,
                (
                    "deterministic vendor container-structure signature match"
                    if deterministic
                    else f"identification method: {device.identification_method or 'unknown'}"
                ),
            )
        else:
            add(
                "Vendor identification",
                "UNKNOWN",
                AccuracyStatus.NOT_APPLICABLE,
                "no vendor-specific structural signature matched this evidence",
            )
        if device is not None and device.confidence is not None:
            add(
                "Identification confidence",
                f"{device.confidence:.2f}",
                AccuracyStatus.OBSERVATION,
                "identification confidence score, not detection accuracy",
                notes="Confidence describes basis strength, not a correctness rate.",
            )

    elif job.job_type == STAGE_RECOVERY:
        recording_ids = json.loads(job.recording_ids) if job.recording_ids else []
        recovery_results = (
            db.query(RecoveryResult).filter(RecoveryResult.recording_id.in_(recording_ids)).all()
            if recording_ids
            else []
        )
        continuity_values = [
            r.frame_continuity for r in recovery_results if r.frame_continuity is not None
        ]
        if continuity_values:
            add(
                "Frame continuity",
                f"{sum(continuity_values) / len(continuity_values):.2f}",
                AccuracyStatus.OBSERVATION,
                "measured directly from the recovered frame counter sequence; no independent ground truth",
            )
        for method in sorted({r.method for r in recovery_results}):
            if method == "vendor_damaged_recovery":
                add(
                    "Recovery method reliability",
                    method,
                    AccuracyStatus.CONTROLLED,
                    "demonstrated against real CP Plus evidence's own genuinely truncated record",
                )
            elif method == "filesystem_index":
                add(
                    "Recovery method reliability",
                    method,
                    AccuracyStatus.NOT_APPLICABLE,
                    "recovery framework only -- not validated against real deleted CP Plus evidence",
                )
            else:
                add(
                    "Recovery method reliability",
                    method,
                    AccuracyStatus.UNVERIFIED,
                    "recovery layer produced output; reliability not independently benchmarked",
                )

    elif job.job_type == STAGE_TIMESTAMP_NORMALIZATION:
        recording_ids = json.loads(job.recording_ids) if job.recording_ids else []
        statuses = (
            sorted(
                {
                    row.value
                    for row in db.query(RecordingMetadata.value)
                    .filter(
                        RecordingMetadata.recording_id.in_(recording_ids),
                        RecordingMetadata.key == "timestamp_normalization_status",
                    )
                    .all()
                    if row.value is not None
                }
            )
            if recording_ids
            else []
        )
        for raw_status in statuses or ["unknown"]:
            accuracy_status, basis = _TIMESTAMP_STATUS_ACCURACY.get(
                raw_status, (AccuracyStatus.NOT_APPLICABLE, "unrecognized status")
            )
            add("Timestamp normalization", raw_status, accuracy_status, basis)

    elif job.job_type == STAGE_AI:
        ai_results = db.query(AIResult).filter(AIResult.job_id == job.id).all()
        if ai_results:
            avg_confidence = sum(r.confidence for r in ai_results) / len(ai_results)
            add(
                "Average detection confidence",
                f"{avg_confidence:.2f}",
                AccuracyStatus.UNVERIFIED,
                "model confidence score; not independently verified and not an accuracy rate",
            )

    elif job.job_type == STAGE_CORRELATION:
        add(
            "Cross-camera correlation candidates",
            job.results_count,
            AccuracyStatus.OBSERVATION,
            "temporal proximity only -- not identity confirmation, not proof of any sequence",
        )

    elif job.job_type == STAGE_VALIDATION:
        metrics = db.query(ValidationMetric).filter(ValidationMetric.job_id == job.id).all()
        for m in metrics:
            add(
                m.metric_name,
                m.metric_value if m.metric_value is not None else "N/A",
                AccuracyStatus.VALIDATED,
                f"measured against ground-truth dataset {m.dataset_id!r}",
                notes=m.notes,
            )

    return rows


def _output_parameters_for_stage(db: Session, job: Job) -> list[OutputParameterResponse]:
    """Real, persisted output values for one pipeline-stage job -- what
    was produced, never how well or how fast. Every branch reads an
    existing model row already written by that stage's own manager."""
    module = _STAGE_TITLES.get(job.job_type, job.job_type.replace("_", " ").title())
    rows: list[OutputParameterResponse] = []

    def add(
        parameter: str, value: object, *, source: str | None = None, notes: str | None = None
    ) -> None:
        rows.append(
            OutputParameterResponse(
                module=module,
                parameter=parameter,
                value=str(value),
                source=source or f"job #{job.id}",
                notes=notes,
            )
        )

    if job.status in _NON_OUTPUT_STATUSES:
        stage_warnings = json.loads(job.warnings) if job.warnings else None
        add(
            "Status",
            job.status.upper(),
            notes="; ".join(stage_warnings) if stage_warnings else None,
        )
        return rows

    if job.job_type == STAGE_INTEGRITY and job.evidence_id is not None:
        hashes = db.query(EvidenceHash).filter(EvidenceHash.evidence_id == job.evidence_id).all()
        for h in hashes:
            add(
                f"{h.algorithm.value.upper()} hash",
                h.hash_value,
                source=f"evidence {job.evidence_id}",
            )
        if not hashes:
            add("Hash", "NOT AVAILABLE")

    elif job.job_type == STAGE_IDENTIFICATION and job.evidence_id is not None:
        device = db.query(Device).filter(Device.evidence_id == job.evidence_id).first()
        for label, value in (
            ("Vendor", device.vendor if device else None),
            ("Model", device.model if device else None),
            ("Firmware", device.firmware if device else None),
            ("Device type", device.device_type if device else None),
        ):
            add(
                label,
                value if value is not None else "NOT AVAILABLE",
                source=f"evidence {job.evidence_id}",
            )

    elif job.job_type in _RESULT_LABELS:
        add(_RESULT_LABELS[job.job_type], job.results_count)
        if job.job_type == STAGE_EXTRACTION:
            recording_ids = json.loads(job.recording_ids) if job.recording_ids else []
            for recording in db.query(Recording).filter(Recording.id.in_(recording_ids)).all():
                add(
                    f"Recording {recording.recording_id} codec/resolution/fps",
                    f"{recording.codec or 'n/a'} · {recording.width or '?'}x{recording.height or '?'} "
                    f"· {recording.fps or 'n/a'} fps · {recording.duration_ms or 'n/a'} ms",
                    source=f"recording {recording.id}",
                )

    elif job.job_type == STAGE_RECOVERY:
        recording_ids = json.loads(job.recording_ids) if job.recording_ids else []
        recovery_results = (
            db.query(RecoveryResult).filter(RecoveryResult.recording_id.in_(recording_ids)).all()
            if recording_ids
            else []
        )
        for r in recovery_results:
            add(
                f"Recovery status (recording {r.recording_id})",
                r.status,
                source=f"recovery result #{r.id}",
            )
            if r.frames_expected is not None or r.frames_recovered is not None:
                recovered_display = (
                    r.frames_recovered if r.frames_recovered is not None else "NOT AVAILABLE"
                )
                expected_display = (
                    r.frames_expected if r.frames_expected is not None else "NOT AVAILABLE"
                )
                add(
                    f"Frames recovered (recording {r.recording_id})",
                    f"{recovered_display}/{expected_display}",
                    source=f"recovery result #{r.id}",
                )
        if not recovery_results:
            add("Recovery attempts", job.results_count)

    elif job.job_type == STAGE_TIMESTAMP_NORMALIZATION:
        recording_ids = json.loads(job.recording_ids) if job.recording_ids else []
        for recording in db.query(Recording).filter(Recording.id.in_(recording_ids)).all():
            add(
                f"Recording {recording.recording_id} normalized start",
                (
                    recording.start_normalized.isoformat()
                    if recording.start_normalized
                    else "NOT AVAILABLE"
                ),
                source=f"recording {recording.id}",
            )
            add(
                f"Recording {recording.recording_id} normalized end",
                (
                    recording.end_normalized.isoformat()
                    if recording.end_normalized
                    else "NOT AVAILABLE"
                ),
                source=f"recording {recording.id}",
            )

    elif job.job_type == STAGE_AI:
        ai_results = db.query(AIResult).filter(AIResult.job_id == job.id).all()
        add("Detections", len(ai_results))
        by_class: dict[str, int] = {}
        for ai_result in ai_results:
            by_class[ai_result.class_name] = by_class.get(ai_result.class_name, 0) + 1
        for class_name, count in sorted(by_class.items()):
            add(f"Detections ({class_name})", count)
        track_count = db.query(AITrack).filter(AITrack.job_id == job.id).count()
        add("Tracks", track_count)

    elif job.job_type == STAGE_VALIDATION:
        metric_count = db.query(ValidationMetric).filter(ValidationMetric.job_id == job.id).count()
        add("Validation metrics computed", metric_count)

    if not rows:
        add("Status", job.status.upper())

    return rows


def _case_level_output_parameters(db: Session, case_id: int) -> list[OutputParameterResponse]:
    """Output parameters that describe the case as a whole rather than any
    one pipeline stage -- audit-chain state, blockchain-anchor state, and
    the most recent report -- none of which are `ProcessingOrchestrator`
    pipeline stages themselves (task: "audit state, blockchain state, ...
    report format")."""
    rows: list[OutputParameterResponse] = []

    chain_result = AuditChainManager.verify_case_chain(db, case_id)
    rows.append(
        OutputParameterResponse(
            module="Audit chain",
            parameter="Chain valid",
            value=str(chain_result.valid),
            source="AuditChainManager.verify_case_chain",
            notes=None if chain_result.valid else f"first failure: {chain_result.failure}",
        )
    )

    anchors = (
        db.query(BlockchainAnchor)
        .filter(BlockchainAnchor.case_id == case_id)
        .order_by(BlockchainAnchor.id.desc())
        .all()
    )
    if anchors:
        latest = anchors[0]
        rows.append(
            OutputParameterResponse(
                module="Blockchain",
                parameter="Latest anchor status",
                value=f"{latest.status} ({latest.provider}/{latest.network})",
                source=f"blockchain anchor #{latest.id}",
            )
        )
        rows.append(
            OutputParameterResponse(
                module="Blockchain",
                parameter="Total anchors",
                value=str(len(anchors)),
                source="blockchain_anchors",
            )
        )
    else:
        rows.append(
            OutputParameterResponse(
                module="Blockchain",
                parameter="Total anchors",
                value="0",
                source="blockchain_anchors",
                notes="no anchor has been created for this case",
            )
        )

    latest_report = (
        db.query(Report).filter(Report.case_id == case_id).order_by(Report.id.desc()).first()
    )
    rows.append(
        OutputParameterResponse(
            module="Report",
            parameter="Latest report",
            value=(
                f"{latest_report.report_type} ({latest_report.status})"
                if latest_report
                else "NOT AVAILABLE"
            ),
            source=f"report #{latest_report.id}" if latest_report else "reports",
            notes=None if latest_report else "no report generated yet for this case",
        )
    )
    return rows


@router.post("/cases/{case_id}/process", response_model=ProcessingRunResponse)
def process_case(
    case_id: int,
    request: ProcessingRunRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    case: Case = Depends(require_case_access),
) -> ProcessingRunResponse:
    """Run controlled automatic processing over every evidence item in a case.

    Runs synchronously within this request (matching every prior phase's
    established pattern -- no background worker exists in this backend).
    Safe to call more than once: see `ProcessingOrchestrator.process_case`'s
    own idempotency documentation.
    """
    del case
    policy = _policy_from_request(request.policy if request else None)
    try:
        summary = ProcessingOrchestrator.process_case(
            db, case_id, policy=policy, triggered_by=current_user
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _run_response(
        summary.root_job,
        new_finding_ids=summary.new_finding_ids,
        notification_ids=summary.notification_ids,
    )


@router.get("/cases/{case_id}/processing", response_model=list[ProcessingRunResponse])
def list_processing_runs(
    case_id: int,
    db: Session = Depends(get_db),
    case: Case = Depends(require_case_access),
) -> list[ProcessingRunResponse]:
    """List every automatic-processing run for a case, most recent first."""
    del case
    runs = ProcessingOrchestrator.list_processing_runs(db, case_id)
    return [_run_response(run) for run in runs]


def _require_processing_run(db: Session, current_user: User, root_job_id: int) -> Job:
    """Shared 404/403 for the three `root_job_id`-keyed routes below.

    Not a `require_case_access_for_job`-style path-param sub-dependency:
    that dependency's parameter is named `job_id`, but this route's path
    parameter is `root_job_id` -- FastAPI only auto-binds a dependency
    parameter to a path segment of the exact same name, so reusing it here
    would silently turn `job_id` into an unrelated, unfulfillable required
    parameter (the same class of bug already caught and fixed for
    `ai.py`/`validation.py`'s body-based `case_id`). Resolving the run
    first and authorizing against its own `case_id` afterward sidesteps
    that entirely, and doubles as the existing "run not found" 404 check.
    """
    run = ProcessingOrchestrator.get_processing_run(db, root_job_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processing run with id {root_job_id} not found",
        )
    try:
        CaseAuthorizationService.require_case_access(db, current_user, run.case_id)
    except CaseAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return run


@router.get("/processing/{root_job_id}", response_model=ProcessingRunResponse)
def get_processing_run(
    root_job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessingRunResponse:
    """Retrieve one processing run's root job and dependency-tracked
    stages -- timing and resource usage only."""
    run = _require_processing_run(db, current_user, root_job_id)
    return _run_response(run)


@router.get("/processing/{root_job_id}/accuracy", response_model=AccuracyValidationResponse)
def get_processing_run_accuracy(
    root_job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccuracyValidationResponse:
    """Every measured quality/validation signal from one processing run,
    deliberately separate from timing (`GET /processing/{id}`) and from
    raw output (`GET /processing/{id}/outputs`). Precision/recall/F1 only
    appear where a real ground-truth dataset backs them; never a single
    universal accuracy percentage."""
    run = _require_processing_run(db, current_user, root_job_id)
    metrics: list[AccuracyMetricResponse] = []
    for stage in sorted(run.child_jobs, key=lambda j: j.id):
        metrics.extend(_accuracy_metrics_for_stage(db, stage))
    return AccuracyValidationResponse(root_job_id=run.id, metrics=metrics)


@router.get("/processing/{root_job_id}/outputs", response_model=OutputParametersResponse)
def get_processing_run_outputs(
    root_job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutputParametersResponse:
    """Every real, persisted output value produced by one processing run
    -- what was produced, never how well or how fast."""
    run = _require_processing_run(db, current_user, root_job_id)
    parameters: list[OutputParameterResponse] = []
    for stage in sorted(run.child_jobs, key=lambda j: j.id):
        parameters.extend(_output_parameters_for_stage(db, stage))
    parameters.extend(_case_level_output_parameters(db, run.case_id))
    return OutputParametersResponse(root_job_id=run.id, parameters=parameters)
