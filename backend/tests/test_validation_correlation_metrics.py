"""Tests for app/validation/correlation_metrics.py (Phase 14) -- the
mandated A -> B -> C cross-camera sequence validation: correct,
incorrect, and incomplete reconstruction. Never an identity claim --
"correctly correlated events" is explicitly distinct from "confirmed
same person" (nothing in this module produces the latter)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.validation.correlation_metrics import (
    SystemSequenceEvent,
    SystemSequenceGroup,
    match_sequences,
    sequence_matches,
)
from app.validation.ground_truth import GroundTruthSequence, GroundTruthSequenceEvent

_T0 = datetime(2026, 8, 30, 10, 0, 12, tzinfo=UTC)

_EXPECTED_ABC = GroundTruthSequence(
    group_reference="SEQ-1",
    events=[
        GroundTruthSequenceEvent(camera_id="A", timestamp=_T0),
        GroundTruthSequenceEvent(camera_id="B", timestamp=_T0 + timedelta(seconds=7)),
        GroundTruthSequenceEvent(camera_id="C", timestamp=_T0 + timedelta(seconds=19)),
    ],
)


def _system_group(
    events: list[SystemSequenceEvent], *, correlation_id: str = "1"
) -> SystemSequenceGroup:
    return SystemSequenceGroup(correlation_id=correlation_id, events=events)


def test_correct_sequence_reconstruction_is_a_true_positive() -> None:
    system_group = _system_group(
        [
            SystemSequenceEvent(camera_id="A", timestamp=_T0),
            SystemSequenceEvent(camera_id="B", timestamp=_T0 + timedelta(seconds=7)),
            SystemSequenceEvent(camera_id="C", timestamp=_T0 + timedelta(seconds=19)),
        ]
    )
    assert sequence_matches(_EXPECTED_ABC, system_group)

    result = match_sequences([_EXPECTED_ABC], [system_group])
    assert result.counts.tp == 1
    assert result.counts.fp == 0
    assert result.counts.fn == 0


def test_incorrect_sequence_wrong_camera_order_is_not_a_match() -> None:
    system_group = _system_group(
        [
            SystemSequenceEvent(camera_id="B", timestamp=_T0),
            SystemSequenceEvent(camera_id="A", timestamp=_T0 + timedelta(seconds=7)),
            SystemSequenceEvent(camera_id="C", timestamp=_T0 + timedelta(seconds=19)),
        ]
    )
    assert not sequence_matches(_EXPECTED_ABC, system_group)

    result = match_sequences([_EXPECTED_ABC], [system_group])
    assert result.counts.tp == 0
    assert result.counts.fp == 1
    assert result.counts.fn == 1


def test_incomplete_sequence_missing_an_event_is_not_a_match() -> None:
    # Only A and C -- B is missing.
    system_group = _system_group(
        [
            SystemSequenceEvent(camera_id="A", timestamp=_T0),
            SystemSequenceEvent(camera_id="C", timestamp=_T0 + timedelta(seconds=19)),
        ]
    )
    assert not sequence_matches(_EXPECTED_ABC, system_group)

    result = match_sequences([_EXPECTED_ABC], [system_group])
    assert result.counts.tp == 0
    assert result.counts.fn == 1
    assert result.counts.fp == 1


def test_no_system_groups_at_all_is_a_false_negative() -> None:
    result = match_sequences([_EXPECTED_ABC], [])
    assert result.counts.tp == 0
    assert result.counts.fn == 1
    assert result.counts.fp == 0


def test_unrelated_system_group_is_a_false_positive() -> None:
    unrelated = _system_group(
        [
            SystemSequenceEvent(camera_id="D", timestamp=_T0 + timedelta(hours=5)),
            SystemSequenceEvent(camera_id="E", timestamp=_T0 + timedelta(hours=5, seconds=10)),
        ]
    )
    result = match_sequences([_EXPECTED_ABC], [unrelated])
    assert result.counts.tp == 0
    assert result.counts.fp == 1
    assert result.counts.fn == 1


def test_timestamp_within_tolerance_still_matches() -> None:
    system_group = _system_group(
        [
            SystemSequenceEvent(camera_id="A", timestamp=_T0 + timedelta(milliseconds=500)),
            SystemSequenceEvent(camera_id="B", timestamp=_T0 + timedelta(seconds=7)),
            SystemSequenceEvent(camera_id="C", timestamp=_T0 + timedelta(seconds=19)),
        ]
    )
    assert sequence_matches(_EXPECTED_ABC, system_group, time_tolerance_seconds=5.0)


def test_timestamp_outside_tolerance_does_not_match() -> None:
    system_group = _system_group(
        [
            SystemSequenceEvent(camera_id="A", timestamp=_T0 + timedelta(seconds=30)),
            SystemSequenceEvent(camera_id="B", timestamp=_T0 + timedelta(seconds=7)),
            SystemSequenceEvent(camera_id="C", timestamp=_T0 + timedelta(seconds=19)),
        ]
    )
    assert not sequence_matches(_EXPECTED_ABC, system_group, time_tolerance_seconds=5.0)


def test_never_produces_an_identity_claim() -> None:
    """Sequence reconstruction is analytical, never identity confirmation."""
    system_group = _system_group(
        [
            SystemSequenceEvent(camera_id="A", timestamp=_T0),
            SystemSequenceEvent(camera_id="B", timestamp=_T0 + timedelta(seconds=7)),
            SystemSequenceEvent(camera_id="C", timestamp=_T0 + timedelta(seconds=19)),
        ]
    )
    result = match_sequences([_EXPECTED_ABC], [system_group])
    blob = str(result).lower()
    for forbidden in ("same person", "identity", "confirmed"):
        assert forbidden not in blob
