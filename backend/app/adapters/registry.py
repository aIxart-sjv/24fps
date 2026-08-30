"""
Vendor-adapter registration, matching, and selection.
Master Specification Section 92 ("Third Backend Milestone"): AdapterRegistry,
`register_adapter(vendor=..., model_pattern=..., firmware_pattern=...)`,
`select_adapter(device_identification_result)`.

In-memory / application-level only — the master specification's database
model (Section 50) defines no persisted "adapters" table, and a registered
adapter's identity is process configuration (which adapter code is
available to this running backend), not per-case forensic data, the same
way FastAPI routes are registered in-process rather than read from a
database. If a future phase needs to persist which adapter/version was
actually used against a specific evidence item, that belongs on
provenance/processing-history records (Section 39/59), not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, IntEnum

from app.adapters.base import AdapterCapability, DVRAdapter, EvidenceBasis, SupportLevel
from app.schemas.device import DeviceIdentificationResult, IdentificationStatus

_GENERIC_MODEL_PATTERN = ".*"


class MatchStrength(IntEnum):
    """How strongly a registered adapter matches an identification result.

    Ordered so a higher value always outranks a lower one — exact
    vendor+model+firmware beats vendor+model, which beats a vendor-level
    generic adapter (Phase 7 task scope, "Matching Priority").
    """

    VENDOR_ONLY = 1
    VENDOR_AND_MODEL = 2
    VENDOR_MODEL_AND_FIRMWARE = 3


class AdapterSelectionStatus(str, Enum):
    """Outcome of an `AdapterRegistry.select_adapter` call."""

    SELECTED = "selected"
    UNKNOWN_VENDOR = "unknown_vendor"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class AdapterMatchAttempt:
    """One registered adapter's match outcome against a single identification result."""

    adapter: DVRAdapter
    matched: bool
    strength: MatchStrength | None
    reason: str


@dataclass(frozen=True)
class AdapterSelectionResult:
    """Result of `AdapterRegistry.select_adapter` — always returned, never raised."""

    status: AdapterSelectionStatus
    adapter: DVRAdapter | None
    reason: str
    attempts: list[AdapterMatchAttempt] = field(default_factory=list)


@dataclass(frozen=True)
class AdapterSupportSummary:
    """One registered adapter's declared support, exactly as that adapter
    reports it (Phase 19 task scope: "registry listing accurately
    reports support levels/capabilities"). Never computed or inferred by
    the registry itself -- every field here is read directly from the
    adapter's own declarative properties."""

    vendor: str
    model_pattern: str
    firmware_pattern: str | None
    model_scope: str
    support_level: SupportLevel
    evidence_basis: tuple[EvidenceBasis, ...]
    capabilities: frozenset[AdapterCapability]
    limitations: tuple[str, ...]
    adapter_version: str


class AdapterRegistry:
    """Registry of vendor adapters, and the sole place adapter selection happens."""

    def __init__(self) -> None:
        self._adapters: list[DVRAdapter] = []

    def register_adapter(self, adapter: DVRAdapter) -> None:
        """Register a vendor adapter.

        Args:
            adapter: The adapter to register. Its `vendor`,
                `model_pattern`, and `firmware_pattern` are read directly
                from the adapter — there is no separate, possibly
                inconsistent set of registration parameters.

        Raises:
            ValueError: If an adapter with the identical
                (vendor, model_pattern, firmware_pattern) identity is
                already registered, or if `model_pattern`/
                `firmware_pattern` is not a valid regular expression.
        """
        try:
            re.compile(adapter.model_pattern)
        except re.error as exc:
            raise ValueError(f"invalid model_pattern {adapter.model_pattern!r}: {exc}") from exc
        if adapter.firmware_pattern is not None:
            try:
                re.compile(adapter.firmware_pattern)
            except re.error as exc:
                raise ValueError(
                    f"invalid firmware_pattern {adapter.firmware_pattern!r}: {exc}"
                ) from exc

        for existing in self._adapters:
            if (
                existing.vendor.lower() == adapter.vendor.lower()
                and existing.model_pattern == adapter.model_pattern
                and existing.firmware_pattern == adapter.firmware_pattern
            ):
                raise ValueError(
                    f"an adapter is already registered for vendor={adapter.vendor!r}, "
                    f"model_pattern={adapter.model_pattern!r}, "
                    f"firmware_pattern={adapter.firmware_pattern!r}"
                )
        self._adapters.append(adapter)

    def list_adapters(self) -> list[DVRAdapter]:
        """Return every registered adapter, in registration order."""
        return list(self._adapters)

    def support_matrix(self) -> list[AdapterSupportSummary]:
        """Return every registered adapter's declared support, in
        registration order (Phase 19 task scope: "Create an explicit
        support matrix"). A vendor with no registered adapter simply does
        not appear here -- this never fabricates an entry for a vendor
        nobody registered."""
        return [
            AdapterSupportSummary(
                vendor=adapter.vendor,
                model_pattern=adapter.model_pattern,
                firmware_pattern=adapter.firmware_pattern,
                model_scope=adapter.model_scope,
                support_level=adapter.support_level,
                evidence_basis=adapter.evidence_basis,
                capabilities=adapter.capabilities,
                limitations=adapter.limitations,
                adapter_version=adapter.adapter_version,
            )
            for adapter in self._adapters
        ]

    def find_matches(self, result: DeviceIdentificationResult) -> list[AdapterMatchAttempt]:
        """Evaluate every registered adapter against `result`.

        Returns:
            One `AdapterMatchAttempt` per registered adapter, in
            registration order, each explaining why it did or did not
            match — the framework's explainability guarantee (Phase 7
            task scope, "Matching Priority": "The registry should be able
            to explain why an adapter matched or why none matched.").
            Never opens or reads the evidence itself — matching uses only
            the already-computed `DeviceIdentificationResult`.
        """
        return [self._evaluate(adapter, result) for adapter in self._adapters]

    def select_adapter(self, result: DeviceIdentificationResult) -> AdapterSelectionResult:
        """Select the single best-matching adapter for `result`.

        Never guesses: if Phase 6 identification itself came back
        `UNKNOWN` or `UNSUPPORTED`, no matching is attempted at all — the
        vendor is unknown, so there is nothing to match against (Master
        Specification Section 55). If identification did produce a vendor
        but no registered adapter matches, the outcome is `UNSUPPORTED`,
        never a silently-chosen generic adapter.

        Args:
            result: The evidence's `DeviceIdentificationResult` (Phase 6).

        Returns:
            A structured `AdapterSelectionResult` — always, never raises
            to signal "no adapter found".
        """
        if result.status in (IdentificationStatus.UNKNOWN, IdentificationStatus.UNSUPPORTED):
            return AdapterSelectionResult(
                status=AdapterSelectionStatus.UNKNOWN_VENDOR,
                adapter=None,
                reason=(
                    f"Phase 6 identification status is {result.status.value!r}; adapter "
                    "selection does not guess a vendor when identification itself did not "
                    "determine one"
                ),
            )

        attempts = self.find_matches(result)
        matching = [attempt for attempt in attempts if attempt.matched]

        if not matching:
            return AdapterSelectionResult(
                status=AdapterSelectionStatus.UNSUPPORTED,
                adapter=None,
                reason=(
                    f"no registered adapter matches vendor={result.vendor!r}, "
                    f"model={result.model!r}, firmware={result.firmware!r}"
                ),
                attempts=attempts,
            )

        top_strength = max(attempt.strength or MatchStrength.VENDOR_ONLY for attempt in matching)
        # Deterministic tie-break: first-registered wins among equal-strength
        # matches, never an arbitrary/unstable choice.
        best = next(attempt for attempt in matching if attempt.strength == top_strength)

        return AdapterSelectionResult(
            status=AdapterSelectionStatus.SELECTED,
            adapter=best.adapter,
            reason=best.reason,
            attempts=attempts,
        )

    def _evaluate(
        self, adapter: DVRAdapter, result: DeviceIdentificationResult
    ) -> AdapterMatchAttempt:
        if not result.vendor:
            return AdapterMatchAttempt(
                adapter=adapter,
                matched=False,
                strength=None,
                reason="identification result has no vendor to match against",
            )
        if adapter.vendor.lower() != result.vendor.lower():
            return AdapterMatchAttempt(
                adapter=adapter,
                matched=False,
                strength=None,
                reason=f"adapter vendor {adapter.vendor!r} does not match {result.vendor!r}",
            )

        is_generic = adapter.model_pattern == _GENERIC_MODEL_PATTERN
        model_matched = False
        if not is_generic:
            if not result.model or not re.fullmatch(adapter.model_pattern, result.model):
                return AdapterMatchAttempt(
                    adapter=adapter,
                    matched=False,
                    strength=None,
                    reason=(
                        f"vendor matched but model {result.model!r} does not match pattern "
                        f"{adapter.model_pattern!r}"
                    ),
                )
            model_matched = True

        firmware_confirmed = False
        if adapter.firmware_pattern is not None and result.firmware is not None:
            if not re.fullmatch(adapter.firmware_pattern, result.firmware):
                return AdapterMatchAttempt(
                    adapter=adapter,
                    matched=False,
                    strength=None,
                    reason=(
                        f"vendor/model matched but firmware {result.firmware!r} does not match "
                        f"pattern {adapter.firmware_pattern!r}"
                    ),
                )
            firmware_confirmed = True

        if model_matched and firmware_confirmed:
            return AdapterMatchAttempt(
                adapter=adapter,
                matched=True,
                strength=MatchStrength.VENDOR_MODEL_AND_FIRMWARE,
                reason=(
                    f"exact match: vendor={adapter.vendor!r}, "
                    f"model pattern={adapter.model_pattern!r}, "
                    f"firmware pattern={adapter.firmware_pattern!r}"
                ),
            )
        if model_matched:
            return AdapterMatchAttempt(
                adapter=adapter,
                matched=True,
                strength=MatchStrength.VENDOR_AND_MODEL,
                reason=(
                    f"vendor+model match: vendor={adapter.vendor!r}, "
                    f"model pattern={adapter.model_pattern!r} (firmware not confirmed)"
                ),
            )
        return AdapterMatchAttempt(
            adapter=adapter,
            matched=True,
            strength=MatchStrength.VENDOR_ONLY,
            reason=f"vendor-only generic match: vendor={adapter.vendor!r}",
        )
