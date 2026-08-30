"""
Cross-camera event correlation (Master Specification Section 29,
"Cross-Camera Correlation"; NTRO requirements section 18, "Event
correlation without AI").

This is an ANALYTICAL correlation engine, never an identity-confirmation
system (Section 29: "Do not overclaim identity. Cross-camera correlation
is an analytical relation, not automatically proof that two detections are
the same real-world person."). Nothing in this module's output vocabulary
implies "same person"/"confirmed"/"identity established" — the strongest
positive status is `RELATED`, describing event compatibility, never a
person.

Pure and deterministic: no DB, no HTTP, no AI/object-detection/tracking
code (Phase 13 territory — see `CorrelationInputEvent.track_reference`/
`movement`, both consumed here only if a caller already has them; nothing
here computes them). `app.core.correlation_manager` is the DB-aware
orchestration layer built on top of this module, mirroring every prior
phase's pure-engine/DB-manager split (Phase 9-11).

Consumes Phase 11's output as-is: `timestamp_status` is one of Phase 11's
`app.timeline.NormalizationStatus` values, read but never recomputed —
this module never calculates or corrects a clock offset, never reinterprets
a CP Plus timestamp, and never applies a timezone conversion.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.recovery.confidence import ConfidenceFactor, compute_confidence

__all__ = [
    "DEFAULT_MAX_GAP_SECONDS",
    "CameraTopology",
    "CorrelationCandidate",
    "CorrelationInputEvent",
    "CorrelationRunResult",
    "CorrelationStatus",
    "PairwiseLink",
    "PairwiseSignals",
    "RecoverySignal",
    "TrackSignal",
    "TriState",
    "correlate",
    "evaluate_pair",
]

#: Maximum gap, in seconds, between two chained events' normalized
#: timestamps for temporal proximity to read `YES`.
#:
#: No document specifies an exact number. Every worked example in both
#: Master Specification Section 29 (18:30:02 -> 18:30:09 -> 18:30:17) and
#: the NTRO requirements' "event correlation without AI" walkthrough
#: (10:00:00 -> 10:00:07 -> 10:00:14) uses ~7-8 second adjacent-camera
#: gaps. 120 seconds is deliberately more generous than those tight
#: examples — real transit between topologically-adjacent-but-not-
#: temporally-tight locations (e.g. a slow walk between an entrance and a
#: lobby) can plausibly take longer than a demo clip — while still small
#: enough that same-day-but-unrelated events do not spuriously chain.
#: Always overridable per call; the *effective* value used is always
#: recorded on `CorrelationRunResult`/`CorrelationCandidate`.
DEFAULT_MAX_GAP_SECONDS = 120.0


class TriState(str, Enum):
    """Shared YES/NO/UNKNOWN vocabulary for the temporal, topology, and
    movement signals (task Phase 12 scope's own testing vocabulary)."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class TrackSignal(str, Enum):
    """Track/object-reference compatibility. Never computed here — only
    consumed if a caller already has track data (Phase 13 territory)."""

    SAME = "same"
    DIFFERENT = "different"
    NOT_AVAILABLE = "not_available"


class RecoverySignal(str, Enum):
    """An event's underlying recording's recovery completeness (Master
    Specification Section 24, "Why recovered footage complicates
    correlation" — timestamp trustworthiness depends on recovery
    completeness). Reported per event, never silently hidden.

    Mapping from `app.recovery.RecoveryStatus` (Phase 10) string values:
    `"recovered"` or no recovery involved at all (`None` — the ordinary,
    non-recovered case) -> `FULL`; `"partial"` -> `PARTIAL`; anything else
    (not attempted, unsupported, no recovery found, failed) or an
    unrecognized value -> `UNKNOWN` (never assumed reliable).
    """

    FULL = "full"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class CorrelationStatus(str, Enum):
    """The result of one correlation judgment (task Phase 12 scope's own
    vocabulary). `RELATED` and `CORRELATED_CANDIDATE` both remain
    analytical relations — neither is an identity claim; `RELATED` simply
    reflects more independently-corroborating signals than
    `CORRELATED_CANDIDATE`.
    """

    RELATED = "related"
    CORRELATED_CANDIDATE = "correlated_candidate"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNRELATED = "unrelated"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CameraTopology:
    """Explicit, examiner-configured camera adjacency.

    Never inferred from camera numbering/ordering (task Phase 12 scope:
    "Do not infer topology merely because cameras are numbered
    sequentially") — every allowed transition must be a caller-supplied
    entry in `transitions`. Directed: `(A, B)` does not imply `(B, A)`
    unless both are explicitly configured.

    `transitions` values are an optional expected movement-direction label
    for that specific transition (e.g. `"east_to_west"`) — only used when
    a caller separately supplies movement data on the events themselves;
    `None` means no expected-direction claim is made for that transition.
    """

    transitions: dict[tuple[str, str], str | None] = field(default_factory=dict)

    def is_allowed(self, from_camera: str, to_camera: str) -> bool:
        """Whether a direct transition from `from_camera` to `to_camera` is configured."""
        return (from_camera, to_camera) in self.transitions

    def expected_movement(self, from_camera: str, to_camera: str) -> str | None:
        """The configured expected movement label for this transition, if any."""
        return self.transitions.get((from_camera, to_camera))


@dataclass(frozen=True)
class CorrelationInputEvent:
    """One event to correlate — the "normalized event" the task's own
    flow diagram names. Every field the caller does not actually have
    stays `None`; nothing here is guessed to fill a gap.
    """

    event_id: str
    case_id: str
    camera_id: str | None
    recording_id: str | None
    event_type: str
    original_timestamp: datetime | None
    normalized_timestamp: datetime | None
    timestamp_status: str | None = None
    recovery_status: str | None = None
    track_reference: str | None = None
    movement: str | None = None
    is_examiner_marker: bool = False


@dataclass(frozen=True)
class PairwiseSignals:
    """The named, explainable signals behind one pairwise correlation judgment."""

    temporal: TriState
    topology: TriState
    movement: TriState
    track: TrackSignal
    gap_seconds: float | None


@dataclass(frozen=True)
class PairwiseLink:
    """One edge in a candidate sequence: the relationship between exactly two events."""

    from_event_id: str
    to_event_id: str
    status: CorrelationStatus
    signals: PairwiseSignals
    confidence: float | None
    confidence_basis: list[str]
    reasons: list[str]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CorrelationCandidate:
    """One correlated investigation sequence (task Phase 12 scope's own
    "CORRELATION-001: Camera 01 -> Camera 02 -> ..." example).

    `event_ids` preserves every source event, in chronological (normalized-
    timestamp) order — never flattened into one synthetic event (task:
    "Keep all source events inside the result. Do not flatten them into
    one synthetic event that loses traceability.").
    """

    event_ids: list[str]
    links: list[PairwiseLink]
    status: CorrelationStatus
    confidence: float | None
    confidence_basis: list[str]
    recovery_signals: dict[str, RecoverySignal]
    max_gap_seconds: float
    method: str = "temporal_topology_deterministic"
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CorrelationRunResult:
    """The full outcome of one `correlate()` call, including the
    processing summary task Phase 12 scope's performance section asks
    for ("number of input events, candidate pairs considered, candidates
    rejected, correlations created, processing time")."""

    candidates: list[CorrelationCandidate]
    input_event_count: int
    events_excluded_no_timestamp: int
    duplicate_events_ignored: int
    candidate_pairs_considered: int
    candidates_rejected: int
    max_gap_seconds: float
    topology_configured: bool
    processing_time_seconds: float


def _recovery_signal(recovery_status: str | None) -> RecoverySignal:
    if recovery_status is None or recovery_status == "recovered":
        return RecoverySignal.FULL
    if recovery_status == "partial":
        return RecoverySignal.PARTIAL
    return RecoverySignal.UNKNOWN


def evaluate_pair(
    from_event: CorrelationInputEvent,
    to_event: CorrelationInputEvent,
    *,
    topology: CameraTopology | None = None,
    max_gap_seconds: float = DEFAULT_MAX_GAP_SECONDS,
) -> PairwiseLink:
    """Evaluate whether two events are compatible with the same investigation sequence.

    This is the single authoritative pairwise judgment — both direct
    pairwise checks and `correlate()`'s bulk chain-building call this same
    function, so there is exactly one place the signal/status rules live.

    Decision rule (deterministic, based on signal presence/absence, never
    a fabricated score):
      1. `temporal == UNKNOWN` (either event lacks a usable normalized
         timestamp) -> `UNKNOWN`: nothing to assess at all.
      2. `temporal == NO` (gap exceeds `max_gap_seconds`) -> `UNRELATED`.
      3. `topology == NO` (topology configured and this transition is not
         one of its entries) -> `UNRELATED` (task: "If topology is
         configured but event order contradicts it: ... reject the
         candidate").
      4. `movement == NO` or `track == DIFFERENT` (positive evidence
         *against* the same sequence) -> `INSUFFICIENT_EVIDENCE`: weaker
         rejection than a configured-topology violation, since movement/
         track data quality is inherently less certain.
      5. Otherwise: `RELATED` if at least two of
         {topology==YES, movement==YES, track==SAME} independently
         corroborate the match, else `CORRELATED_CANDIDATE` (temporal
         proximity alone, or temporal plus exactly one corroborating
         signal).

    Args:
        from_event: The chronologically earlier event.
        to_event: The chronologically later event.
        topology: Configured camera adjacency, or `None` if no topology
            was supplied (reported as `UNKNOWN`, never inferred).
        max_gap_seconds: The effective temporal window for this call.

    Returns:
        A `PairwiseLink` with the full signal breakdown and reasons.
    """
    reasons: list[str] = []
    warnings: list[str] = []

    gap_seconds: float | None = None
    if from_event.normalized_timestamp is None or to_event.normalized_timestamp is None:
        temporal = TriState.UNKNOWN
        temporal_reason = "temporal correlation unavailable: missing normalized timestamp"
        warnings.append(temporal_reason)
    else:
        gap_seconds = (
            to_event.normalized_timestamp - from_event.normalized_timestamp
        ).total_seconds()
        if 0 <= gap_seconds <= max_gap_seconds:
            temporal = TriState.YES
            temporal_reason = (
                f"temporal: {gap_seconds:.0f}s apart, within the {max_gap_seconds:.0f}s window"
            )
        else:
            temporal = TriState.NO
            temporal_reason = (
                f"temporal: {gap_seconds:.0f}s apart, outside the {max_gap_seconds:.0f}s window"
            )
        reasons.append(temporal_reason)

    # Consume (never recompute) Phase 11's normalization status: an
    # event whose normalized timestamp is not `verified` still
    # participates in temporal matching (Phase 11 already decided it is
    # usable), but that fact is surfaced here for traceability rather
    # than silently treated as equally trustworthy as a verified one.
    for label, ev in (("from_event", from_event), ("to_event", to_event)):
        if ev.timestamp_status is not None and ev.timestamp_status != "verified":
            warnings.append(
                f"{label} {ev.event_id!r} normalized timestamp status is "
                f"{ev.timestamp_status!r}, not 'verified'"
            )

    from_cam, to_cam = from_event.camera_id, to_event.camera_id
    if topology is None:
        topology_signal = TriState.UNKNOWN
        warnings.append("topology unavailable: no camera topology was supplied")
    elif from_cam is None or to_cam is None:
        topology_signal = TriState.UNKNOWN
        warnings.append("topology unavailable: one or both events have no camera_id")
    elif from_cam == to_cam:
        topology_signal = TriState.UNKNOWN
    elif topology.is_allowed(from_cam, to_cam):
        topology_signal = TriState.YES
        reasons.append(f"topology: {from_cam!r} -> {to_cam!r} is a configured transition")
    else:
        topology_signal = TriState.NO
        reasons.append(f"topology: {from_cam!r} -> {to_cam!r} is not a configured transition")

    if from_event.movement is None or to_event.movement is None:
        movement_signal = TriState.UNKNOWN
    else:
        expected = (
            topology.expected_movement(from_cam, to_cam)
            if topology is not None and from_cam is not None and to_cam is not None
            else None
        )
        if expected is None:
            movement_signal = TriState.UNKNOWN
            warnings.append(
                "movement unavailable: no expected direction configured for this transition"
            )
        elif from_event.movement == expected:
            movement_signal = TriState.YES
            reasons.append(f"movement: {from_event.movement!r} matches the expected direction")
        else:
            movement_signal = TriState.NO
            reasons.append(
                f"movement: {from_event.movement!r} conflicts with expected {expected!r}"
            )

    if from_event.track_reference is None or to_event.track_reference is None:
        track_signal = TrackSignal.NOT_AVAILABLE
    elif from_event.track_reference == to_event.track_reference:
        track_signal = TrackSignal.SAME
        reasons.append(f"track: same reference {from_event.track_reference!r}")
    else:
        track_signal = TrackSignal.DIFFERENT
        reasons.append("track: different references")

    signals = PairwiseSignals(
        temporal=temporal,
        topology=topology_signal,
        movement=movement_signal,
        track=track_signal,
        gap_seconds=gap_seconds,
    )

    if temporal == TriState.UNKNOWN:
        status = CorrelationStatus.UNKNOWN
    elif temporal == TriState.NO:
        status = CorrelationStatus.UNRELATED
    elif topology_signal == TriState.NO:
        status = CorrelationStatus.UNRELATED
    elif movement_signal == TriState.NO or track_signal == TrackSignal.DIFFERENT:
        status = CorrelationStatus.INSUFFICIENT_EVIDENCE
    else:
        corroborating = sum(
            (
                topology_signal == TriState.YES,
                movement_signal == TriState.YES,
                track_signal == TrackSignal.SAME,
            )
        )
        status = (
            CorrelationStatus.RELATED
            if corroborating >= 2
            else CorrelationStatus.CORRELATED_CANDIDATE
        )

    confidence_result = compute_confidence(
        [
            ConfidenceFactor(
                name="temporal",
                weight=2.0,
                value=1.0 if temporal == TriState.YES else None,
                basis=temporal_reason,
            ),
            ConfidenceFactor(
                name="topology",
                weight=2.0,
                value=(
                    1.0
                    if topology_signal == TriState.YES
                    else (0.0 if topology_signal == TriState.NO else None)
                ),
                basis="camera topology compatibility",
            ),
            ConfidenceFactor(
                name="movement",
                weight=1.0,
                value=(
                    1.0
                    if movement_signal == TriState.YES
                    else (0.0 if movement_signal == TriState.NO else None)
                ),
                basis="movement direction compatibility",
            ),
            ConfidenceFactor(
                name="track",
                weight=1.5,
                value=(
                    1.0
                    if track_signal == TrackSignal.SAME
                    else (0.0 if track_signal == TrackSignal.DIFFERENT else None)
                ),
                basis="track/object reference compatibility",
            ),
        ]
    )

    return PairwiseLink(
        from_event_id=from_event.event_id,
        to_event_id=to_event.event_id,
        status=status,
        signals=signals,
        confidence=confidence_result.confidence,
        confidence_basis=confidence_result.basis,
        reasons=reasons,
        warnings=warnings,
    )


def correlate(
    events: list[CorrelationInputEvent],
    *,
    topology: CameraTopology | None = None,
    max_gap_seconds: float = DEFAULT_MAX_GAP_SECONDS,
) -> CorrelationRunResult:
    """Group events from multiple cameras into candidate investigation sequences.

    Deterministic, bounded-window chain-building — not naive O(n^2)
    pairwise comparison (task Phase 12 scope's performance section):
    events are sorted once by `(normalized_timestamp, event_id)` (never
    input/DB order), then scanned once, extending whichever currently-open
    chain has the smallest valid gap to the new event. A chain closes
    (stops being extendable) as soon as an event's gap to its last member
    exceeds `max_gap_seconds` — since events are processed in ascending
    time order, every later event's gap to that same chain is only ever
    larger, so this is a safe, one-time closure.

    Args:
        events: The events to correlate. May be unordered and may contain
            duplicate `event_id`s (task: "Duplicate input must not create
            duplicate correlation groups", "The correlation engine must
            handle unordered input").
        topology: Configured camera adjacency, or `None`.
        max_gap_seconds: The temporal window. See `DEFAULT_MAX_GAP_SECONDS`
            for the documented default and its rationale.

    Returns:
        A `CorrelationRunResult`. Candidates of length < 2 are never
        produced (nothing to correlate with just one event).
    """
    started = time.monotonic()

    seen_ids: set[str] = set()
    deduplicated: list[CorrelationInputEvent] = []
    duplicate_count = 0
    for event in events:
        if event.event_id in seen_ids:
            duplicate_count += 1
            continue
        seen_ids.add(event.event_id)
        deduplicated.append(event)

    usable = [e for e in deduplicated if e.normalized_timestamp is not None]
    excluded_count = len(deduplicated) - len(usable)
    usable.sort(key=lambda e: (e.normalized_timestamp, e.event_id))

    chains: list[list[CorrelationInputEvent]] = []
    chain_links: list[list[PairwiseLink]] = []
    open_indices: list[int] = []
    pairs_considered = 0
    pairs_rejected = 0

    for event in usable:
        still_open: list[int] = []
        best_idx: int | None = None
        best_link: PairwiseLink | None = None
        for idx in open_indices:
            last = chains[idx][-1]
            pairs_considered += 1
            link = evaluate_pair(last, event, topology=topology, max_gap_seconds=max_gap_seconds)
            if link.signals.gap_seconds is not None and link.signals.gap_seconds > max_gap_seconds:
                # This chain can never be extended again (times only advance).
                pairs_rejected += 1
                continue
            still_open.append(idx)
            if link.status not in (
                CorrelationStatus.CORRELATED_CANDIDATE,
                CorrelationStatus.RELATED,
            ):
                pairs_rejected += 1
                continue
            if best_link is None or (link.signals.gap_seconds or 0) < (
                best_link.signals.gap_seconds or 0
            ):
                best_idx, best_link = idx, link
        open_indices = still_open

        if best_idx is not None and best_link is not None:
            chains[best_idx].append(event)
            chain_links[best_idx].append(best_link)
        else:
            chains.append([event])
            chain_links.append([])
            open_indices.append(len(chains) - 1)

    candidates: list[CorrelationCandidate] = []
    for chain, links in zip(chains, chain_links, strict=True):
        if len(chain) < 2:
            continue
        statuses = [link.status for link in links]
        overall_status = min(statuses, key=lambda s: _STATUS_STRENGTH[s])
        confidences = [link.confidence for link in links if link.confidence is not None]
        overall_confidence = min(confidences) if confidences else None
        basis: list[str] = []
        for link in links:
            basis.extend(link.confidence_basis)
        recovery_signals = {e.event_id: _recovery_signal(e.recovery_status) for e in chain}
        warnings: list[str] = []
        for link in links:
            warnings.extend(link.warnings)
        candidates.append(
            CorrelationCandidate(
                event_ids=[e.event_id for e in chain],
                links=links,
                status=overall_status,
                confidence=overall_confidence,
                confidence_basis=basis,
                recovery_signals=recovery_signals,
                max_gap_seconds=max_gap_seconds,
                warnings=warnings,
            )
        )

    return CorrelationRunResult(
        candidates=candidates,
        input_event_count=len(events),
        events_excluded_no_timestamp=excluded_count,
        duplicate_events_ignored=duplicate_count,
        candidate_pairs_considered=pairs_considered,
        candidates_rejected=pairs_rejected,
        max_gap_seconds=max_gap_seconds,
        topology_configured=topology is not None,
        processing_time_seconds=time.monotonic() - started,
    )


_STATUS_STRENGTH: dict[CorrelationStatus, int] = {
    CorrelationStatus.RELATED: 4,
    CorrelationStatus.CORRELATED_CANDIDATE: 3,
    CorrelationStatus.INSUFFICIENT_EVIDENCE: 2,
    CorrelationStatus.UNKNOWN: 1,
    CorrelationStatus.UNRELATED: 0,
}
