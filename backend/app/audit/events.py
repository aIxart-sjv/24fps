"""
Processing-event vocabulary (Phase 15, Master Specification Section 39
"Provenance Engine"; task Phase 15 scope sections 3-5).

Pure, DB-free, HTTP-free: just the controlled vocabulary
`app.core.provenance_manager.ProvenanceManager.record_event` validates
against. No processing logic lives here -- Phase 15 only records the
history of operations Phases 8-14 already perform, it never reimplements
them.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["ActorType", "ProcessingOperation"]


class ProcessingOperation(str, Enum):
    """The pipeline stages a `ProcessingEvent` may record (task Phase 15
    scope section 4's own list). Recording history for one of these never
    reimplements it -- Phase 15 only observes and logs what Phases 8-14
    already did.
    """

    ACQUISITION = "acquisition"
    IDENTIFICATION = "identification"
    PARSING = "parsing"
    EXTRACTION = "extraction"
    RECOVERY = "recovery"
    TIMESTAMP_NORMALIZATION = "timestamp_normalization"
    TIMELINE = "timeline"
    AI_ANALYSIS = "ai_analysis"
    VALIDATION = "validation"
    CORRELATION = "correlation"
    ARTIFACT_GENERATION = "artifact_generation"
    #: Phase 17: submitting a chain-state fingerprint to a blockchain
    #: provider (Master Specification Section 50's job-type vocabulary
    #: lists "blockchain_anchor"). Recording this never reimplements
    #: anchoring -- `app.core.blockchain_manager.BlockchainManager` does.
    BLOCKCHAIN_ANCHOR = "blockchain_anchor"
    #: Phase 18: assembling and rendering a standardized report from
    #: existing case state (Master Specification Section 50's job-type
    #: vocabulary lists "report"). Recording this never reimplements
    #: report generation -- `app.core.report_manager.ReportManager` does.
    REPORT = "report"
    #: Phase 21: a completed physical evidence custody handoff (QR-based
    #: chain of custody). Recorded once per *completed* transfer only --
    #: never for a still-`PENDING` one -- by `app.core.custody_manager.
    #: CustodyManager`, which owns physical custody state; this value only
    #: lets that completion appear in the existing Phase 15/16 audit
    #: chain, it never reimplements hashing/chaining/verification.
    PHYSICAL_CUSTODY_TRANSFER = "physical_custody_transfer"
    #: Phase 22: one controlled, automatic case-processing run performed by
    #: `app.core.processing_orchestrator.ProcessingOrchestrator` (the root
    #: run, or one of its dependency-tracked pipeline stages). Recording
    #: this never reimplements any of the phases it coordinates -- it only
    #: records that the orchestrator invoked them and what happened.
    ORCHESTRATION = "orchestration"
    #: Phase 22: the findings engine (`app.core.findings_engine.
    #: FindingsEngine`) generating or updating a structured `Finding` from
    #: an already-computed result. Distinct from `ORCHESTRATION` so a
    #: case's audit history can distinguish "a pipeline stage ran" from
    #: "that stage's result was judged worth an examiner's attention".
    FINDING_GENERATION = "finding_generation"
    #: Phase 25: an administrator granting or revoking one user's access
    #: to a case (`app.core.case_authorization_service.
    #: CaseAuthorizationService`). One value covers both directions --
    #: `grant`/`revoke` plus the target user are recorded in `parameters`
    #: (matching the existing coarse-operation/detailed-parameters split
    #: every other operation here already uses) -- so a case's audit
    #: history shows exactly who could open it and when that changed, and
    #: participates in the same hash-linked chain as every other event
    #: (task section 11: tampering with an access-change event must be
    #: detectable the same way as any other).
    CASE_ACCESS_CHANGE = "case_access_change"


class ActorType(str, Enum):
    """Who/what performed a processing operation.

    Task Phase 15 scope section 5: "Never claim an automated process was
    performed by a human." `ProvenanceManager.record_event` requires this
    explicitly from every caller -- it is never inferred or defaulted, so
    a wrong guess can never mislabel automated work as human-performed.
    """

    HUMAN = "human"
    SYSTEM = "system"
