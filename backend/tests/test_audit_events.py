"""Tests for app/audit/events.py (Phase 15) -- pure vocabulary sanity."""

from __future__ import annotations

from app.audit.events import ActorType, ProcessingOperation


def test_processing_operation_matches_the_documented_vocabulary() -> None:
    expected = {
        "acquisition",
        "identification",
        "parsing",
        "extraction",
        "recovery",
        "timestamp_normalization",
        "timeline",
        "ai_analysis",
        "validation",
        "correlation",
        "artifact_generation",
        # Phase 17: submitting a chain-state fingerprint to a blockchain
        # provider (Master Specification Section 50's job-type vocabulary).
        "blockchain_anchor",
        # Phase 18: assembling/rendering a standardized report (Master
        # Specification Section 50's job-type vocabulary).
        "report",
        # Phase 21: a completed physical evidence custody handoff
        # (QR-based chain of custody).
        "physical_custody_transfer",
        # Phase 22: one automatic case-processing orchestration run.
        "orchestration",
        # Phase 22: the findings engine generating/updating a finding.
        "finding_generation",
        # Phase 25: an admin granting/revoking a user's case access.
        "case_access_change",
    }
    assert {op.value for op in ProcessingOperation} == expected


def test_actor_type_has_exactly_human_and_system() -> None:
    assert {a.value for a in ActorType} == {"human", "system"}


def test_no_processing_operation_value_implies_an_identity_claim() -> None:
    for op in ProcessingOperation:
        for forbidden in ("person", "identity", "name", "face"):
            assert forbidden not in op.value
