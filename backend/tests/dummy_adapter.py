"""
TEST/DEMONSTRATION ADAPTER ONLY.

This is not a real vendor adapter and must never be registered outside
tests. It exists solely to prove the Phase 7 vendor-adapter framework
(registration, matching, selection, capability inspection, unsupported
behavior) without any proprietary DVR/NVR parsing — every `DVRAdapter`
operation method is left at its base-class default
(`AdapterCapabilityNotImplementedError`), and this class overrides none of
them, by design.
"""

from __future__ import annotations

from app.adapters.base import AdapterCapability, DVRAdapter, EvidenceBasis, SupportLevel


class DummyAdapter(DVRAdapter):
    """A configurable stand-in adapter for exercising `AdapterRegistry`.

    Vendor/model/firmware identity and declared capabilities are all
    supplied by the test, so one class can represent many different
    hypothetical registrations without needing a distinct subclass per
    scenario.
    """

    def __init__(
        self,
        *,
        vendor: str,
        model_pattern: str = ".*",
        firmware_pattern: str | None = None,
        capabilities: frozenset[AdapterCapability] = frozenset(),
        adapter_version: str = "0.0.1-test",
        support_level: SupportLevel = SupportLevel.LEVEL_0_RESEARCH_ONLY,
        evidence_basis: tuple[EvidenceBasis, ...] = (EvidenceBasis.INFERENCE,),
    ) -> None:
        self._vendor = vendor
        self._model_pattern = model_pattern
        self._firmware_pattern = firmware_pattern
        self._capabilities = capabilities
        self._adapter_version = adapter_version
        self._support_level = support_level
        self._evidence_basis = evidence_basis

    @property
    def vendor(self) -> str:
        return self._vendor

    @property
    def model_pattern(self) -> str:
        return self._model_pattern

    @property
    def firmware_pattern(self) -> str | None:
        return self._firmware_pattern

    @property
    def capabilities(self) -> frozenset[AdapterCapability]:
        return self._capabilities

    @property
    def adapter_version(self) -> str:
        return self._adapter_version

    @property
    def support_level(self) -> SupportLevel:
        return self._support_level

    @property
    def evidence_basis(self) -> tuple[EvidenceBasis, ...]:
        return self._evidence_basis
