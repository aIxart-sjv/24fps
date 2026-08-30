"""Tests for app/audit/chain_of_custody.py (Phase 15) -- pure vocabulary
sanity."""

from __future__ import annotations

from app.audit.chain_of_custody import CustodyEventType


def test_custody_event_type_matches_the_documented_vocabulary() -> None:
    expected = {
        "evidence_received",
        "evidence_registered",
        "image_created",
        "hash_calculated",
        "evidence_mounted",
        "parser_started",
        "parser_completed",
        "recovery_started",
        "recovery_completed",
        "ai_started",
        "ai_completed",
        "report_generated",
        "evidence_exported",
    }
    assert {e.value for e in CustodyEventType} == expected


def test_started_and_completed_variants_are_paired() -> None:
    values = {e.value for e in CustodyEventType}
    for prefix in ("parser", "recovery", "ai"):
        assert f"{prefix}_started" in values
        assert f"{prefix}_completed" in values
