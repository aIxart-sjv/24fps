"""Tests for app/timeline/correlation.py (Phase 12) — the pure,
deterministic cross-camera correlation engine. No DB, no HTTP.

Covers every category the Phase 12 task explicitly requires: the
documented A->B->C scenario and the A/D-outside-window scenario (with
their exact timestamps), temporal proximity, topology compatible/
incompatible/missing, movement compatible/incompatible/unknown, track
same/different/not-available, missing normalized timestamp, duplicate
events, unordered input, an unrelated event between two valid candidates,
recovery-status propagation, and an explicit assertion that no output
text anywhere implies identity confirmation.
"""

from __future__ import annotations

from datetime import datetime

from app.timeline.correlation import (
    DEFAULT_MAX_GAP_SECONDS,
    CameraTopology,
    CorrelationInputEvent,
    CorrelationStatus,
    RecoverySignal,
    TrackSignal,
    TriState,
    correlate,
    evaluate_pair,
)


def _event(
    event_id: str,
    camera_id: str | None,
    timestamp: str,
    *,
    recovery_status: str | None = None,
    track_reference: str | None = None,
    movement: str | None = None,
    normalized_timestamp: str | None = "__default__",
) -> CorrelationInputEvent:
    """Build a `CorrelationInputEvent` with a normalized timestamp parsed from
    an ISO string (default: the same value passed as `timestamp`)."""
    normalized = timestamp if normalized_timestamp == "__default__" else normalized_timestamp
    return CorrelationInputEvent(
        event_id=event_id,
        case_id="1",
        camera_id=camera_id,
        recording_id=None,
        event_type="test_event",
        original_timestamp=datetime.fromisoformat(timestamp),
        normalized_timestamp=(datetime.fromisoformat(normalized) if normalized else None),
        recovery_status=recovery_status,
        track_reference=track_reference,
        movement=movement,
    )


# --- The task's own controlled test scenarios (exact timestamps) ---------


def test_a_b_c_scenario_produces_one_correlated_candidate() -> None:
    events = [
        _event("A1", "A", "2026-08-30T10:00:12+00:00"),
        _event("B1", "B", "2026-08-30T10:00:19+00:00"),
        _event("C1", "C", "2026-08-30T10:00:31+00:00"),
    ]
    topology = CameraTopology(transitions={("A", "B"): None, ("B", "C"): None})

    result = correlate(events, topology=topology)

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.event_ids == ["A1", "B1", "C1"]
    # Topology corroborates but movement/track do not -> exactly one
    # corroborating signal -> CORRELATED_CANDIDATE, not the stronger RELATED.
    assert candidate.status == CorrelationStatus.CORRELATED_CANDIDATE


def test_events_outside_temporal_window_are_not_correlated() -> None:
    events = [
        _event("A1", "A", "2026-08-30T10:00:12+00:00"),
        _event("D1", "D", "2026-08-30T10:10:00+00:00"),
    ]

    result = correlate(events)

    assert result.candidates == []


def test_a_b_c_scenario_with_missing_topology_is_reported_unavailable() -> None:
    events = [
        _event("A1", "A", "2026-08-30T10:00:12+00:00"),
        _event("B1", "B", "2026-08-30T10:00:19+00:00"),
        _event("C1", "C", "2026-08-30T10:00:31+00:00"),
    ]

    result = correlate(events, topology=None)

    assert result.topology_configured is False
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.status == CorrelationStatus.CORRELATED_CANDIDATE
    for link in candidate.links:
        assert link.signals.topology == TriState.UNKNOWN
        assert any("topology unavailable" in w for w in link.warnings)


def test_strong_multi_signal_match_is_still_not_identity_confirmation() -> None:
    """Object class match (same track) + close timestamps + compatible
    topology corroborate strongly, but must never read as identity
    confirmation — only the strongest analytical status, RELATED."""
    topology = CameraTopology(transitions={("A", "B"): "north"})
    events = [
        _event("A1", "A", "2026-08-30T10:00:00+00:00", track_reference="T1", movement="north"),
        _event("B1", "B", "2026-08-30T10:00:07+00:00", track_reference="T1", movement="north"),
    ]

    result = correlate(events, topology=topology)

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.status == CorrelationStatus.RELATED

    texts: list[str] = [candidate.status.value, *candidate.warnings, *candidate.confidence_basis]
    for link in candidate.links:
        texts.extend([link.status.value, *link.reasons, *link.warnings, *link.confidence_basis])
    blob = " ".join(texts).lower()
    for forbidden in ("same person", "identity", "confirmed"):
        assert forbidden not in blob


# --- Topology signal -------------------------------------------------------


def test_topology_incompatible_transition_is_unrelated() -> None:
    topology = CameraTopology(transitions={("A", "B"): None})
    a = _event("A1", "A", "2026-08-30T10:00:00+00:00")
    x = _event("X1", "X", "2026-08-30T10:00:05+00:00")

    link = evaluate_pair(a, x, topology=topology)

    assert link.signals.topology == TriState.NO
    assert link.status == CorrelationStatus.UNRELATED


def test_topology_not_inferred_from_camera_numbering() -> None:
    """Cameras named to look sequential must not be treated as adjacent
    unless explicitly configured (task: never infer topology from
    numbering)."""
    topology = CameraTopology(transitions={("cam-1", "cam-2"): None})
    a = _event("A1", "cam-2", "2026-08-30T10:00:00+00:00")
    b = _event("B1", "cam-3", "2026-08-30T10:00:05+00:00")

    link = evaluate_pair(a, b, topology=topology)

    assert link.signals.topology == TriState.NO
    assert link.status == CorrelationStatus.UNRELATED


# --- Movement signal ---------------------------------------------------


def test_movement_compatible_with_configured_direction() -> None:
    topology = CameraTopology(transitions={("A", "B"): "north"})
    a = _event("A1", "A", "2026-08-30T10:00:00+00:00", movement="north")
    b = _event("B1", "B", "2026-08-30T10:00:05+00:00", movement="north")

    link = evaluate_pair(a, b, topology=topology)

    assert link.signals.movement == TriState.YES


def test_movement_incompatible_yields_insufficient_evidence() -> None:
    topology = CameraTopology(transitions={("A", "B"): "north"})
    a = _event("A1", "A", "2026-08-30T10:00:00+00:00", movement="south")
    b = _event("B1", "B", "2026-08-30T10:00:05+00:00", movement="south")

    link = evaluate_pair(a, b, topology=topology)

    assert link.signals.movement == TriState.NO
    assert link.status == CorrelationStatus.INSUFFICIENT_EVIDENCE


def test_movement_unknown_when_not_supplied() -> None:
    topology = CameraTopology(transitions={("A", "B"): "north"})
    a = _event("A1", "A", "2026-08-30T10:00:00+00:00")
    b = _event("B1", "B", "2026-08-30T10:00:05+00:00")

    link = evaluate_pair(a, b, topology=topology)

    assert link.signals.movement == TriState.UNKNOWN


# --- Track/object reference signal --------------------------------------


def test_track_same_reference() -> None:
    a = _event("A1", "A", "2026-08-30T10:00:00+00:00", track_reference="T1")
    b = _event("B1", "B", "2026-08-30T10:00:05+00:00", track_reference="T1")

    link = evaluate_pair(a, b)

    assert link.signals.track == TrackSignal.SAME


def test_track_different_reference_yields_insufficient_evidence() -> None:
    a = _event("A1", "A", "2026-08-30T10:00:00+00:00", track_reference="T1")
    b = _event("B1", "B", "2026-08-30T10:00:05+00:00", track_reference="T2")

    link = evaluate_pair(a, b)

    assert link.signals.track == TrackSignal.DIFFERENT
    assert link.status == CorrelationStatus.INSUFFICIENT_EVIDENCE


def test_track_not_available_when_neither_event_has_one() -> None:
    a = _event("A1", "A", "2026-08-30T10:00:00+00:00")
    b = _event("B1", "B", "2026-08-30T10:00:05+00:00")

    link = evaluate_pair(a, b)

    assert link.signals.track == TrackSignal.NOT_AVAILABLE


# --- Missing data / duplicates / ordering -------------------------------


def test_missing_normalized_timestamp_excludes_event_but_is_counted() -> None:
    events = [
        _event("A1", "A", "2026-08-30T10:00:00+00:00"),
        _event("B1", "B", "2026-08-30T10:00:05+00:00", normalized_timestamp=None),
    ]

    result = correlate(events)

    assert result.input_event_count == 2
    assert result.events_excluded_no_timestamp == 1
    assert result.candidates == []


def test_duplicate_events_do_not_create_duplicate_candidates() -> None:
    events = [
        _event("A1", "A", "2026-08-30T10:00:00+00:00"),
        _event("B1", "B", "2026-08-30T10:00:05+00:00"),
        _event("A1", "A", "2026-08-30T10:00:00+00:00"),
    ]

    result = correlate(events)

    assert result.duplicate_events_ignored == 1
    assert len(result.candidates) == 1
    assert result.candidates[0].event_ids == ["A1", "B1"]


def test_unordered_input_produces_the_same_result_as_sorted_input() -> None:
    a = _event("A1", "A", "2026-08-30T10:00:12+00:00")
    b = _event("B1", "B", "2026-08-30T10:00:19+00:00")
    c = _event("C1", "C", "2026-08-30T10:00:31+00:00")
    topology = CameraTopology(transitions={("A", "B"): None, ("B", "C"): None})

    sorted_result = correlate([a, b, c], topology=topology)
    shuffled_result = correlate([c, a, b], topology=topology)

    assert [cand.event_ids for cand in sorted_result.candidates] == [
        cand.event_ids for cand in shuffled_result.candidates
    ]


def test_unrelated_intervening_event_does_not_break_a_b_link() -> None:
    topology = CameraTopology(transitions={("A", "B"): None})
    events = [
        _event("A1", "A", "2026-08-30T10:00:00+00:00"),
        _event("X1", "X", "2026-08-30T10:00:05+00:00"),
        _event("B1", "B", "2026-08-30T10:00:10+00:00"),
    ]

    result = correlate(events, topology=topology)

    assert len(result.candidates) == 1
    assert result.candidates[0].event_ids == ["A1", "B1"]


# --- Recovery-status propagation ----------------------------------------


def test_partial_recovery_status_is_propagated_not_hidden() -> None:
    events = [
        _event("A1", "A", "2026-08-30T10:00:00+00:00", recovery_status="partial"),
        _event("B1", "B", "2026-08-30T10:00:05+00:00"),
    ]

    result = correlate(events)

    candidate = result.candidates[0]
    assert candidate.recovery_signals["A1"] == RecoverySignal.PARTIAL
    assert candidate.recovery_signals["B1"] == RecoverySignal.FULL


# --- Processing summary / observability ---------------------------------


def test_run_result_reports_the_processing_summary() -> None:
    events = [
        _event("A1", "A", "2026-08-30T10:00:00+00:00"),
        _event("B1", "B", "2026-08-30T10:00:05+00:00"),
    ]

    result = correlate(events)

    assert result.processing_time_seconds >= 0
    assert result.max_gap_seconds == DEFAULT_MAX_GAP_SECONDS
    assert result.candidate_pairs_considered >= 1


# --- Vocabulary safety ----------------------------------------------------


def test_status_vocabulary_never_implies_identity_confirmation() -> None:
    forbidden = ("same person", "identity", "confirmed")
    for status in CorrelationStatus:
        value = status.value.lower()
        for term in forbidden:
            assert term not in value
