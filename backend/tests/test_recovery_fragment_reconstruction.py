"""Tests for generic fragment-map assembly (app/recovery/fragment_reconstruction.py), Phase 10."""

from __future__ import annotations

from app.recovery.fragment_reconstruction import (
    FragmentLink,
    FragmentLinkOutcome,
    build_fragment_map,
)


def test_fragment_map_fully_continuous():
    links = [
        FragmentLink("seg1", "seg2", FragmentLinkOutcome.CONTINUOUS, "ok"),
        FragmentLink("seg2", "seg3", FragmentLinkOutcome.CONTINUOUS, "ok"),
    ]
    fmap = build_fragment_map(["seg1", "seg2", "seg3"], links)
    assert fmap.is_fully_continuous is True
    assert fmap.missing_intervals == []
    assert fmap.warnings == []


def test_fragment_map_reports_gap_as_missing_interval_and_warning():
    links = [
        FragmentLink("seg1", "seg2", FragmentLinkOutcome.CONTINUOUS, "ok"),
        FragmentLink("seg2", "seg3", FragmentLinkOutcome.GAP, "seg between 2 and 3 not found"),
    ]
    fmap = build_fragment_map(["seg1", "seg2", "seg3"], links)
    assert fmap.is_fully_continuous is False
    assert fmap.missing_intervals == ["seg between 2 and 3 not found"]
    assert fmap.warnings == ["seg between 2 and 3 not found"]


def test_fragment_map_overlap_and_duplicate_are_warnings_not_missing_intervals():
    links = [
        FragmentLink("seg1", "seg2", FragmentLinkOutcome.OVERLAP, "overlap detected"),
        FragmentLink("seg2", "seg3", FragmentLinkOutcome.DUPLICATE, "duplicate segment"),
    ]
    fmap = build_fragment_map(["seg1", "seg2", "seg3"], links)
    assert fmap.missing_intervals == []
    assert fmap.warnings == ["overlap detected", "duplicate segment"]


def test_fragment_map_single_fragment_has_no_links():
    fmap = build_fragment_map(["only"], [])
    assert fmap.is_fully_continuous is True
    assert fmap.links == []
    assert fmap.warnings == []
