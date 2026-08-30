"""
Generic recovery-confidence scoring.
Master Specification Section 22 ("Recovery Confidence"): "Confidence
should be based on actual evidence, not a fabricated number," with a
documented `basis` list explaining what it was built from. This module
supplies the combination mechanism only — every actual factor value must
come from something a caller genuinely measured (e.g.
`app.recovery.continuity`, real NAL-unit presence, real footer/length
validity) — nothing here invents a number.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConfidenceFactor:
    """One measured (or explicitly unmeasured) input to a confidence score.

    `value` is `None` when this factor could not be measured for the case
    at hand (e.g. no counters to compare) — such factors are excluded from
    the weighted average entirely, rather than being treated as 0.
    """

    name: str
    weight: float
    value: float | None
    basis: str


@dataclass(frozen=True)
class ConfidenceResult:
    """A combined confidence score plus the exact factors it was built from."""

    confidence: float | None
    factors: list[ConfidenceFactor] = field(default_factory=list)

    @property
    def basis(self) -> list[str]:
        """Human-readable basis strings for every factor that was actually measured."""
        return [f.basis for f in self.factors if f.value is not None]


def compute_confidence(factors: list[ConfidenceFactor]) -> ConfidenceResult:
    """Combine `factors` into a single weighted-average confidence score.

    Args:
        factors: The evidence-based factors to combine. Each `value` must
            already be a real measurement in `[0.0, 1.0]`, or `None` if
            this factor is not applicable/measurable for this case.

    Returns:
        A `ConfidenceResult`. `confidence` is `None` when no factor could
        be measured at all (nothing to base a number on) — never a
        fabricated default.

    Raises:
        ValueError: If any factor's `weight` is negative, or a non-`None`
            `value` is outside `[0.0, 1.0]`.
    """
    for factor in factors:
        if factor.weight < 0:
            raise ValueError(f"factor {factor.name!r} has a negative weight")
        if factor.value is not None and not (0.0 <= factor.value <= 1.0):
            raise ValueError(f"factor {factor.name!r} has value {factor.value} outside [0, 1]")

    measured = [f for f in factors if f.value is not None]
    total_weight = sum(f.weight for f in measured)
    if not measured or total_weight <= 0:
        return ConfidenceResult(confidence=None, factors=factors)

    weighted_sum = sum((f.value or 0.0) * f.weight for f in measured)
    return ConfidenceResult(confidence=weighted_sum / total_weight, factors=factors)
