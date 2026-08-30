"""
Generic frame/counter continuity math.
Master Specification Section 22 ("Recovery Confidence"): "frame continuity"
is one of the listed, evidence-based confidence factors. Section 24
("Fragment Reconstruction") lists "gaps/corruption" as a required output.

This module works on plain integer sequences (e.g. CPV record `counter`
values) — it has no knowledge of any specific vendor's container format,
so it is reusable by any adapter that exposes a monotonic per-unit counter.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContinuityResult:
    """Continuity of an ordered sequence of integer counters.

    `gaps` lists every `(previous_counter, next_counter)` pair where the
    counter did not advance by exactly 1 — a direct, computed fact, not an
    estimate.
    """

    total_steps: int
    continuous_steps: int
    gaps: list[tuple[int, int]] = field(default_factory=list)

    @property
    def continuity_fraction(self) -> float | None:
        """Fraction of adjacent steps with no gap, or `None` if there were
        fewer than 2 counters to compare (continuity is undefined)."""
        if self.total_steps == 0:
            return None
        return self.continuous_steps / self.total_steps


def measure_counter_continuity(counters: list[int]) -> ContinuityResult:
    """Measure how many adjacent pairs in `counters` advance by exactly 1.

    Args:
        counters: An ordered sequence of integer counters (e.g. each valid
            CPV record's `counter` field, in file order).

    Returns:
        A `ContinuityResult`. `total_steps` is `len(counters) - 1` (or 0
        for fewer than 2 counters) — never divides by zero, never
        estimates a continuity fraction with no data to base it on.
    """
    if len(counters) < 2:
        return ContinuityResult(total_steps=0, continuous_steps=0, gaps=[])

    total_steps = len(counters) - 1
    continuous_steps = 0
    gaps: list[tuple[int, int]] = []
    for previous, current in zip(counters, counters[1:], strict=False):
        if current - previous == 1:
            continuous_steps += 1
        else:
            gaps.append((previous, current))

    return ContinuityResult(total_steps=total_steps, continuous_steps=continuous_steps, gaps=gaps)
