"""Tests for app/validation/tracking_metrics.py (Phase 14) -- track
continuity: coverage, fragmentation, missed frames. Never an identity
claim."""

from __future__ import annotations

import dataclasses

from app.validation.ground_truth import GroundTruthTrack
from app.validation.tracking_metrics import SystemTrack, evaluate_track_continuity


def test_track_continuity_result_has_no_identity_field() -> None:
    from app.validation.tracking_metrics import TrackContinuityResult

    field_names = {f.name for f in dataclasses.fields(TrackContinuityResult)}
    for forbidden in ("identity", "person_name", "embedding"):
        assert forbidden not in field_names


def test_full_coverage_by_a_single_system_track() -> None:
    gt = GroundTruthTrack(class_name="person", first_seen_frame=0, last_seen_frame=9)
    system_tracks = [
        SystemTrack(class_name="person", first_seen_frame=0, last_seen_frame=9, frame_count=10)
    ]
    result = evaluate_track_continuity(gt, system_tracks)
    assert result.coverage_fraction == 1.0
    assert result.fragmentation_count == 1
    assert result.missed_frames == 0
    assert result.class_match is True


def test_missing_track_yields_zero_coverage() -> None:
    gt = GroundTruthTrack(class_name="person", first_seen_frame=0, last_seen_frame=9)
    result = evaluate_track_continuity(gt, [])
    assert result.coverage_fraction == 0.0
    assert result.fragmentation_count == 0
    assert result.missed_frames == 10


def test_fragmented_track_across_two_system_tracks() -> None:
    gt = GroundTruthTrack(class_name="person", first_seen_frame=0, last_seen_frame=9)
    system_tracks = [
        SystemTrack(class_name="person", first_seen_frame=0, last_seen_frame=4, frame_count=5),
        SystemTrack(class_name="person", first_seen_frame=5, last_seen_frame=9, frame_count=5),
    ]
    result = evaluate_track_continuity(gt, system_tracks)
    assert result.fragmentation_count == 2
    assert result.coverage_fraction == 1.0
    assert result.missed_frames == 0


def test_partial_coverage_with_a_gap_reports_missed_frames() -> None:
    gt = GroundTruthTrack(class_name="person", first_seen_frame=0, last_seen_frame=9)
    system_tracks = [
        SystemTrack(class_name="person", first_seen_frame=0, last_seen_frame=3, frame_count=4),
        SystemTrack(class_name="person", first_seen_frame=7, last_seen_frame=9, frame_count=3),
    ]
    result = evaluate_track_continuity(gt, system_tracks)
    assert result.covered_frames == 4 + 3
    assert result.missed_frames == 10 - 7


def test_class_mismatch_is_reported() -> None:
    gt = GroundTruthTrack(class_name="person", first_seen_frame=0, last_seen_frame=9)
    system_tracks = [
        SystemTrack(class_name="car", first_seen_frame=0, last_seen_frame=9, frame_count=10)
    ]
    result = evaluate_track_continuity(gt, system_tracks)
    assert result.class_match is False


def test_frame_overlap_tolerance_widens_matching() -> None:
    gt = GroundTruthTrack(class_name="person", first_seen_frame=10, last_seen_frame=20)
    system_tracks = [
        SystemTrack(class_name="person", first_seen_frame=0, last_seen_frame=8, frame_count=9)
    ]
    strict = evaluate_track_continuity(gt, system_tracks, frame_overlap_tolerance=0)
    lenient = evaluate_track_continuity(gt, system_tracks, frame_overlap_tolerance=2)
    assert strict.fragmentation_count == 0
    assert lenient.fragmentation_count == 1
