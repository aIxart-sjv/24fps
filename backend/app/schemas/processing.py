"""
Pydantic schemas for the automatic case-processing API (Phase 22, revised
Phase 24-2: "Processing Performance, Accuracy/Validation, and Output
Parameter tables from REAL runtime data").

Three deliberately separate response shapes, matching that task's own
"Do not mix performance and accuracy into one metric" rule:

- `ProcessingStageResponse`/`ProcessingRunResponse`: HOW LONG and with
  WHAT RESOURCES did each stage run -- timing and machine resource usage
  only, never a correctness/quality judgment.
- `AccuracyMetricResponse`/`AccuracyValidationResponse`: HOW GOOD was the
  output -- precision/recall/F1 only where a ground-truth basis exists,
  confidence always labeled as confidence (never accuracy), each row
  carrying an explicit `status` from a closed vocabulary so a reader
  never has to guess how much to trust a number.
- `OutputParameterResponse`/`OutputParametersResponse`: WHAT did the
  stage actually produce -- vendor/model, recording/detection/track
  counts, codec/resolution, recovery status, audit/blockchain state,
  artifact hashes, report format, etc. No quality claim of any kind.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.job import JobResponse


class ProcessingPolicyRequest(BaseModel):
    """Optional overrides for `app.core.processing_policy.ProcessingPolicy`.
    Every field defaults to that dataclass's own documented default when
    omitted -- see its module docstring for the automation-tier rationale
    behind each default."""

    run_extraction: bool = True
    run_recovery: bool = True
    run_timestamp_normalization: bool = True
    run_ai: bool = False
    ai_analysis_types: list[str] | None = None
    run_correlation: bool = True
    run_validation: bool = True
    force_reprocess: bool = False
    notify: bool = True


class ProcessingRunRequest(BaseModel):
    """Request body for `POST /cases/{case_id}/process`. All fields optional
    -- an empty body runs the default policy."""

    policy: ProcessingPolicyRequest | None = None


class ProcessingStageResponse(BaseModel):
    """One dependency-tracked pipeline-stage job within a processing run --
    timing and resource usage only (task: "Processing Performance ... from
    REAL runtime data"; "Do not mix performance and accuracy into one
    metric" -- correctness/quality never appears here)."""

    id: int
    job_type: str
    status: str
    evidence_id: int | None
    recording_ids: list[int] | None
    progress: float | None
    results_count: int
    error: str | None
    warnings: list[str] | None
    started_at: str | None
    completed_at: str | None
    #: The stage's real measured runtime in seconds. Sourced from
    #: `time.perf_counter()` deltas captured directly around the stage
    #: (`app.core.resource_metrics`, high-resolution, monotonic, immune
    #: to wall-clock adjustments) whenever that measurement was recorded;
    #: falls back to the coarser `completed_at - started_at` wall-clock
    #: subtraction only for a job row that predates/opted out of that
    #: measurement (`high_resolution_timing=False` on that same row) --
    #: never a fabricated or estimated duration either way.
    duration_seconds: float | None
    #: `True` when `duration_seconds` came from the high-resolution
    #: `perf_counter()` measurement; `False` when it is the coarser
    #: wall-clock fallback; `None` when no duration is available at all.
    high_resolution_timing: bool | None
    #: Real process CPU time (user-mode) consumed during this stage's
    #: measured interval, in seconds -- `resource.getrusage` deltas. Since
    #: this backend runs every stage synchronously in one thread (no
    #: background worker anywhere), this delta genuinely reflects only
    #: this stage's own CPU activity. `None` when unmeasured.
    cpu_user_seconds: float | None
    #: Real process CPU time (kernel-mode) for the same interval.
    cpu_system_seconds: float | None
    #: `resource.getrusage().ru_maxrss` as of this stage's completion --
    #: the process's peak resident-set size in KB *since process start*
    #: (Linux; monotonically non-decreasing), NOT this stage's own
    #: exclusive peak. `None` when unmeasured.
    peak_rss_kb: int | None
    #: Real, point-in-time resident-set-size delta (`/proc/self/status`
    #: `VmRSS`, end minus start) across this stage's interval -- unlike
    #: `peak_rss_kb`, this genuinely isolates memory growth attributable
    #: to this stage. `None` when unmeasured or unreadable on this
    #: platform (never a guess).
    rss_delta_kb: int | None
    #: What this stage actually read as input (e.g.
    #: `"evidence_source_file"`, `"derived_media_artifact"`,
    #: `"timeline_events"`, `"ground_truth_rows"`). `None` when not
    #: applicable to this stage.
    input_type: str | None
    #: The real, on-disk/measured size of that input -- see
    #: `input_size_unit` for what the number counts. `None` when not
    #: applicable or not resolvable (e.g. the source file was missing).
    input_size: int | None
    #: Unit for `input_size`: `"bytes"`, `"events"`, or `"rows"`.
    input_size_unit: str | None


class ProcessingRunResponse(BaseModel):
    """The root orchestration run plus its dependency-tracked children and
    observability counters (task Phase 22 scope, "Observability")."""

    root_job: JobResponse
    stages: list[ProcessingStageResponse]
    stages_total: int
    stages_completed: int
    stages_failed: int
    stages_skipped: int
    stages_blocked: int
    stages_requires_review: int
    new_finding_ids: list[int] = Field(default_factory=list)
    notification_ids: list[int] = Field(default_factory=list)
    #: Sum of every stage's own `duration_seconds` (never a wall-clock
    #: measurement of the whole run, which would also count time this
    #: process spent scheduling/committing between stages) -- see
    #: `high_resolution_timing` on the summed stages for whether that sum
    #: is high-resolution throughout. `None` while the run has not
    #: finished, or no stage reported a duration.
    total_duration_seconds: float | None


class AccuracyStatus(str, Enum):
    """Closed vocabulary for how much basis backs one accuracy/validation
    row (task: "report status such as VALIDATED / CONTROLLED / OBSERVATION
    / UNVERIFIED / N/A where appropriate"). Never inferred beyond this
    module's own documented mapping in
    `app.api.routes.processing._accuracy_metrics_for_stage`.

    - VALIDATED: checked against an independent, authoritative reference
      (a real ground-truth dataset's precision/recall/F1, a cryptographic
      hash/audit-chain verification, a deterministic vendor-structure
      signature match).
    - CONTROLLED: produced by a real, demonstrated capability whose
      reliability is documented against controlled/real test evidence,
      but not independently re-verified for this specific run.
    - OBSERVATION: a real, measured value with no correctness claim
      attached at all (a rate, a count, a continuity score).
    - UNVERIFIED: a real value that exists but has not been independently
      checked (e.g. an AI detection confidence score).
    - N/A: the metric does not apply / was not run / has no basis yet.
    """

    VALIDATED = "VALIDATED"
    CONTROLLED = "CONTROLLED"
    OBSERVATION = "OBSERVATION"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "N/A"


class AccuracyMetricResponse(BaseModel):
    """One accuracy/quality/validation signal from a single pipeline
    stage -- deliberately separate from both timing
    (`ProcessingStageResponse`) and raw output (`OutputParameterResponse`).
    Precision/recall/F1 appear here ONLY when a real `ValidationMetric`
    row (backed by an actual `GroundTruth` dataset) produced them; a
    confidence score is always labeled as confidence, never as accuracy;
    nothing here is ever a single universal percentage standing in for
    "how good is this case"."""

    module: str
    metric: str
    value: str
    status: AccuracyStatus
    #: Plain-language basis for `status` -- what specifically was
    #: compared against what (e.g. `"ground truth dataset 'ds-1'"`,
    #: `"SHA-256 recomputation"`, `"no independent verification"`).
    basis: str
    source: str
    notes: str | None = None


class AccuracyValidationResponse(BaseModel):
    """Every measured accuracy/quality/validation signal produced by one
    processing run."""

    root_job_id: int
    metrics: list[AccuracyMetricResponse]


class OutputParameterResponse(BaseModel):
    """One real, persisted output value from a single pipeline stage --
    what was produced, never how well or how fast (task: "aggregate real
    persisted outputs from each module")."""

    module: str
    parameter: str
    value: str
    source: str
    notes: str | None = None


class OutputParametersResponse(BaseModel):
    """Every real output parameter produced by one processing run."""

    root_job_id: int
    parameters: list[OutputParameterResponse]
