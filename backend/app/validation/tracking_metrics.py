"""
Tracking validation (Phase 14, Master Specification Section 32; task
Phase 14 scope section 11).

Validates track CONTINUITY -- frame coverage, fragmentation, missed
frames -- never identity (Master Specification Section 32: "Tracking
does not automatically prove identity."). A ground-truth track describes
one continuously-present object's expected frame range; the system may
have represented that continuity as a single track, or split it into
several (an "ID switch," NTRO requirements Section 49 terminology) -- this
module quantifies exactly that, without ever asserting who the object was.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.validation.ground_truth import GroundTruthTrack

__all__ = ["SystemTrack", "TrackContinuityResult", "evaluate_track_continuity"]


@dataclass(frozen=True)
class SystemTrack:
    """One system-produced track's frame coverage (as persisted on
    `app.models.ai_result.AITrack`)."""

    class_name: str
    first_seen_frame: int
    last_seen_frame: int
    frame_count: int


@dataclass(frozen=True)
class TrackContinuityResult:
    """How well a set of system tracks covers one expected ground-truth track."""

    ground_truth: GroundTruthTrack
    matched_system_tracks: list[SystemTrack]
    expected_frame_span: int
    covered_frames: int
    coverage_fraction: float | None
    #: How many distinct system tracks overlapped the expected span. `0`
    #: means the track was entirely missed; `1` means clean, unbroken
    #: coverage; `>1` means the expected continuity was fragmented across
    #: multiple system track IDs.
    fragmentation_count: int
    missed_frames: int
    class_match: bool


def evaluate_track_continuity(
    ground_truth: GroundTruthTrack,
    system_tracks: list[SystemTrack],
    *,
    frame_overlap_tolerance: int = 0,
) -> TrackContinuityResult:
    """Evaluate how completely `system_tracks` cover one expected ground-truth track.

    Args:
        ground_truth: The independently-known expected track (frame span
            + expected class).
        system_tracks: Every system-produced track that might relate to
            this expected one (e.g. every `AITrack` on the same recording
            with an overlapping frame range).
        frame_overlap_tolerance: Extra frames of slack allowed when
            deciding whether a system track "overlaps" the expected span
            (e.g. sampling-induced boundary rounding). `0` by default --
            always recorded as a validation parameter.

    Returns:
        A `TrackContinuityResult` with frame coverage, fragmentation
        count, and missed-frame count -- never an identity claim.
    """
    expected_start = ground_truth.first_seen_frame
    expected_end = ground_truth.last_seen_frame
    expected_span = max(expected_end - expected_start + 1, 0)

    overlapping = [
        track
        for track in system_tracks
        if track.last_seen_frame + frame_overlap_tolerance >= expected_start
        and track.first_seen_frame - frame_overlap_tolerance <= expected_end
    ]

    clipped_intervals = sorted(
        (max(track.first_seen_frame, expected_start), min(track.last_seen_frame, expected_end))
        for track in overlapping
    )

    covered = 0
    current_end = expected_start - 1
    for start, end in clipped_intervals:
        start = max(start, current_end + 1)
        if start > end:
            continue
        covered += end - start + 1
        current_end = end

    covered = min(covered, expected_span)
    missed = max(expected_span - covered, 0)
    coverage_fraction = covered / expected_span if expected_span > 0 else None
    class_match = bool(overlapping) and all(
        track.class_name == ground_truth.class_name for track in overlapping
    )

    return TrackContinuityResult(
        ground_truth=ground_truth,
        matched_system_tracks=overlapping,
        expected_frame_span=expected_span,
        covered_frames=covered,
        coverage_fraction=coverage_fraction,
        fragmentation_count=len(overlapping),
        missed_frames=missed,
        class_match=class_match,
    )
