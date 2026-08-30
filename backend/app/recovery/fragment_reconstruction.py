"""
Generic fragment-map assembly.
Master Specification Section 24 ("Fragment Reconstruction"): outputs are
"reconstructed fragment map, missing intervals, reconstruction confidence,
warnings." This module only assembles that output shape from
*already-computed* adjacent-fragment relationships — determining those
relationships (e.g. CPV outer-header counter chaining) is vendor-specific
evidence work that belongs in each adapter's own `recovery.py` (Phase 8's
`app.adapters.cp_plus.session.link_cpv_session`, reused as-is, not
reimplemented here).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FragmentLinkOutcome(str, Enum):
    """The vendor-agnostic classification of one adjacent fragment pair's relationship."""

    CONTINUOUS = "continuous"
    GAP = "gap"
    OVERLAP = "overlap"
    DUPLICATE = "duplicate"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FragmentLink:
    """The relationship found between two adjacent fragments, already determined
    by vendor-specific evidence (e.g. a counter/offset chain)."""

    previous_label: str
    next_label: str
    outcome: FragmentLinkOutcome
    detail: str


@dataclass(frozen=True)
class FragmentMap:
    """The reconstructed relationship between an ordered set of fragments."""

    fragment_labels: list[str]
    links: list[FragmentLink] = field(default_factory=list)
    missing_intervals: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_fully_continuous(self) -> bool:
        """Whether every adjacent pair links as `CONTINUOUS` (no gaps/overlaps/duplicates)."""
        return all(link.outcome == FragmentLinkOutcome.CONTINUOUS for link in self.links)


def build_fragment_map(fragment_labels: list[str], links: list[FragmentLink]) -> FragmentMap:
    """Assemble a `FragmentMap` from already-computed adjacent-pair link outcomes.

    Args:
        fragment_labels: The fragments' identifiers, in the order they are
            asserted to belong (the caller's provenance — this function
            does not reorder them).
        links: One `FragmentLink` per adjacent pair in `fragment_labels`
            (i.e. `len(links) == max(0, len(fragment_labels) - 1)`),
            already classified by vendor-specific evidence.

    Returns:
        A `FragmentMap`. `missing_intervals` collects every `GAP` link's
        detail text; `warnings` collects every non-`CONTINUOUS` link's
        detail text (gaps included) — nothing here infers or guesses a
        relationship beyond what `links` already asserts.
    """
    missing_intervals = [link.detail for link in links if link.outcome == FragmentLinkOutcome.GAP]
    warnings = [link.detail for link in links if link.outcome != FragmentLinkOutcome.CONTINUOUS]
    return FragmentMap(
        fragment_labels=list(fragment_labels),
        links=list(links),
        missing_intervals=missing_intervals,
        warnings=warnings,
    )
