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


class ActorType(str, Enum):
    """Who/what performed a processing operation.

    Task Phase 15 scope section 5: "Never claim an automated process was
    performed by a human." `ProvenanceManager.record_event` requires this
    explicitly from every caller -- it is never inferred or defaulted, so
    a wrong guess can never mislabel automated work as human-performed.
    """

    HUMAN = "human"
    SYSTEM = "system"
