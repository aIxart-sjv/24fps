"""
Automatic case-processing policy (Phase 22).
Master Specification Section 57 ("Forensic Workflow Orchestrator").

This module holds nothing but the *decision knobs* `app.core.
processing_orchestrator.ProcessingOrchestrator` reads before running a
step -- it never itself opens evidence, calls a manager, or touches the
database. Splitting policy out from the orchestrator keeps "what may run
automatically" (this file, and the docstring below) separate from "how a
step that is allowed to run actually runs" (the orchestrator).

Task Phase 22 scope, "Automation Policy": operations are grouped into
three tiers. This backend has no background worker/task queue (confirmed
during the Phase 22 gap assessment -- every prior phase's "job" is created
and run to completion inside the same call, Phase 13's `AIManager.run_job`
docstring documents this explicitly), so "queued" below means "the
orchestrator still runs it inline, but only when this flag opts in" --
never a fabricated async queue (task Phase 22 scope, "Performance/Async":
"Do not fake asynchronous execution").

AUTOMATIC / SAFE TO RUN (always attempted, no flag -- each of these reads
existing state or performs a read-only/idempotent, non-destructive
operation against original evidence):
    - evidence integrity hash/verify
    - device identification + storage/format detection
    - recording enumeration (a clean no-op for unsupported evidence --
      `RecordingManager.enumerate_recordings`'s own documented contract)
    - timeline ingestion (idempotent upsert)
    - audit-chain verification (read-only)

CONDITIONALLY AUTOMATIC / policy-gated (each defaults to a documented
value below, but a caller may opt out or, for AI, opt in):
    - extraction (`run_extraction`, default `True` -- required before
      every later stage; the only "expensive" default-on step, but never
      run for evidence enumeration itself already reported empty)
    - recovery (`run_recovery`, default `True` -- Phase 10's engine only
      reads original evidence and writes new artifacts, never mutates the
      source, and only runs at all against evidence enumeration already
      confirmed is CP-Plus-shaped)
    - timestamp normalization (`run_timestamp_normalization`, default
      `True` -- safe with no inputs at all; resolves to `UNKNOWN` rather
      than failing when `reference_timezone`/`reference` are not supplied)
    - AI analysis (`run_ai`, default `False` -- task Phase 22 scope,
      "AI Automation": model inference is the one step this codebase
      cannot bound the cost of ahead of time, so it stays opt-in)
    - cross-camera correlation (`run_correlation`, default `True` -- but
      the orchestrator itself still only actually runs it when >= 2
      distinct camera/event sources exist; see task Phase 22 scope,
      "Correlation Automation")
    - validation (`run_validation`, default `True` -- but only actually
      runs a metric computation when a ground-truth dataset already
      exists for the case; never invents one)

EXAMINER-CONTROLLED / never automatic, regardless of policy (no flag can
enable these -- an examiner uses the existing dedicated endpoint):
    - choosing a validation ground-truth dataset
    - blockchain anchoring of case state (`app.core.blockchain_manager.
      BlockchainManager.create_anchor` remains a deliberate, separate
      examiner action; Section 32 forbids anchoring "every intermediate
      job")
    - report generation (`app.core.report_manager.ReportManager.
      generate_report` remains a deliberate, separate examiner action)
    - final evidentiary interpretation (never automated by this or any
      phase)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

__all__ = ["DEFAULT_AI_ANALYSIS_TYPES", "ProcessingPolicy"]

#: Deliberately lightweight when AI is opted in without an explicit
#: `ai_analysis_types` override -- object + motion detection only, no
#: tracking/face detection, which keeps an opt-in automatic run cheap by
#: default (task Phase 22 scope, "No 'Run Everything' Blindly"). An
#: examiner wanting more uses the existing `POST /api/v1/ai/jobs` route
#: directly, unconstrained by this policy.
DEFAULT_AI_ANALYSIS_TYPES: tuple[str, ...] = ("object_detection", "motion_detection")


@dataclass(frozen=True)
class ProcessingPolicy:
    """One case-processing run's explicit, recorded set of automation
    decisions (task Phase 22 scope, "The exact automatic set must be
    recorded in the processing run" -- `ProcessingOrchestrator` stores
    `as_dict()` on the root `Job.parameters`)."""

    run_extraction: bool = True
    run_recovery: bool = True
    run_timestamp_normalization: bool = True
    run_ai: bool = False
    ai_analysis_types: tuple[str, ...] = DEFAULT_AI_ANALYSIS_TYPES
    run_correlation: bool = True
    run_validation: bool = True
    #: Re-run a stage even if a prior successful attempt already exists
    #: for the same evidence/recording (task Phase 22 scope,
    #: "Idempotency": "explicitly create a new processing job/version when
    #: rerun is required"). `False` reuses/reports existing results.
    force_reprocess: bool = False
    #: Create `Notification` rows for findings generated by this run.
    notify: bool = True

    def as_dict(self) -> dict[str, object]:
        """Plain-value form for `Job.parameters`/API responses."""
        data = asdict(self)
        data["ai_analysis_types"] = list(self.ai_analysis_types)
        return data

    @staticmethod
    def from_dict(data: dict[str, object]) -> ProcessingPolicy:
        """Reconstruct a policy from a decoded `Job.parameters` dict,
        ignoring unknown keys so a future field addition never breaks
        reading an older, already-persisted run."""
        known = set(ProcessingPolicy.__dataclass_fields__)
        kwargs = {key: value for key, value in data.items() if key in known}
        if "ai_analysis_types" in kwargs and kwargs["ai_analysis_types"] is not None:
            kwargs["ai_analysis_types"] = tuple(kwargs["ai_analysis_types"])  # type: ignore[arg-type]
        return ProcessingPolicy(**kwargs)  # type: ignore[arg-type]
