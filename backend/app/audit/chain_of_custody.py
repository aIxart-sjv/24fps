"""
Chain-of-custody event vocabulary (Phase 15, Master Specification Section
40 "Chain of Custody").

Pure, DB-free, HTTP-free: the controlled vocabulary for evidence-
lifecycle milestones (as distinct from `app.audit.events.
ProcessingOperation`'s broader pipeline-stage vocabulary). Both enums'
`.value` strings are valid `ProcessingEvent.operation` values -- a caller
records either a pipeline-stage event or an evidence-lifecycle milestone
through the same `ProvenanceManager.record_event` call; the column itself
stays a plain string (no DB-level constraint), matching the established
convention from `GroundTruth.event_type`/`ValidationMetric.
validation_type` (Phase 14).

This module does not implement the hash-linked chain itself (Master
Specification Section 41) -- `ProcessingEvent.previous_hash`/
`current_hash` exist as documented columns but stay `NULL` here; Phase 16
(`app.audit.hash_chain`, still an empty stub) computes and populates them.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["CustodyEventType"]


class CustodyEventType(str, Enum):
    """Evidence-lifecycle milestones (Master Specification Section 40's
    own example list). "The system should not allow silent deletion/
    editing of forensic history" -- every value here names a discrete,
    already-happened fact, never a claim about ongoing state.
    """

    EVIDENCE_RECEIVED = "evidence_received"
    EVIDENCE_REGISTERED = "evidence_registered"
    IMAGE_CREATED = "image_created"
    HASH_CALCULATED = "hash_calculated"
    EVIDENCE_MOUNTED = "evidence_mounted"
    PARSER_STARTED = "parser_started"
    PARSER_COMPLETED = "parser_completed"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    AI_STARTED = "ai_started"
    AI_COMPLETED = "ai_completed"
    REPORT_GENERATED = "report_generated"
    EVIDENCE_EXPORTED = "evidence_exported"
