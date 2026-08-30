"""Tests for the five research-only (Level 0) Phase 19 adapters:
Honeywell, Uniview, TP-Link, Godrej, Matrix. These have zero detection/
parsing capability by design -- these tests exist specifically to prove
the system never falsely claims support for them (task Phase 19 scope:
"If a vendor has only Level 0/1 research support: tests must verify that
the system DOES NOT falsely claim full support").
"""

from __future__ import annotations

import pytest

from app.adapters.base import (
    AdapterCapabilityNotImplementedError,
    DVRAdapter,
    EvidenceBasis,
    SupportLevel,
)
from app.adapters.godrej import GodrejAdapter
from app.adapters.honeywell import HoneywellAdapter
from app.adapters.matrix import MatrixAdapter
from app.adapters.tp_link import TPLinkAdapter
from app.adapters.uniview import UniviewAdapter

_RESEARCH_ONLY_ADAPTERS: list[tuple[type[DVRAdapter], str]] = [
    (HoneywellAdapter, "Honeywell Security"),
    (UniviewAdapter, "Uniview"),
    (TPLinkAdapter, "TP-Link"),
    (GodrejAdapter, "Godrej"),
    (MatrixAdapter, "Matrix"),
]


@pytest.mark.parametrize("adapter_cls,expected_vendor", _RESEARCH_ONLY_ADAPTERS)
def test_vendor_identity(adapter_cls: type[DVRAdapter], expected_vendor: str) -> None:
    adapter = adapter_cls()
    assert adapter.vendor == expected_vendor


@pytest.mark.parametrize("adapter_cls,_vendor", _RESEARCH_ONLY_ADAPTERS)
def test_declares_zero_capabilities(adapter_cls: type[DVRAdapter], _vendor: str) -> None:
    adapter = adapter_cls()
    assert adapter.capabilities == frozenset()


@pytest.mark.parametrize("adapter_cls,_vendor", _RESEARCH_ONLY_ADAPTERS)
def test_support_level_is_research_only(adapter_cls: type[DVRAdapter], _vendor: str) -> None:
    adapter = adapter_cls()
    assert adapter.support_level == SupportLevel.LEVEL_0_RESEARCH_ONLY
    assert adapter.support_level < SupportLevel.LEVEL_1_DETECTION


@pytest.mark.parametrize("adapter_cls,_vendor", _RESEARCH_ONLY_ADAPTERS)
def test_evidence_basis_is_never_real_project_evidence(
    adapter_cls: type[DVRAdapter], _vendor: str
) -> None:
    adapter = adapter_cls()
    assert EvidenceBasis.REAL_PROJECT_EVIDENCE not in adapter.evidence_basis
    assert len(adapter.evidence_basis) > 0  # never an unexplained empty tuple


@pytest.mark.parametrize("adapter_cls,_vendor", _RESEARCH_ONLY_ADAPTERS)
def test_limitations_are_never_empty(adapter_cls: type[DVRAdapter], _vendor: str) -> None:
    adapter = adapter_cls()
    assert len(adapter.limitations) > 0
    assert any("REAL VALIDATION PENDING" in lim for lim in adapter.limitations)


@pytest.mark.parametrize("adapter_cls,_vendor", _RESEARCH_ONLY_ADAPTERS)
def test_no_operation_method_silently_succeeds(adapter_cls: type[DVRAdapter], _vendor: str) -> None:
    """Every Section-16 operation method must raise the clean
    "not implemented" signal -- never fabricate a result, never crash
    with an unrelated exception."""
    adapter = adapter_cls()
    for call in (
        lambda: adapter.identify(),
        lambda: adapter.detect_capabilities(),
        lambda: adapter.inspect_storage(),
        lambda: adapter.parse_filesystem(),
        lambda: adapter.parse_metadata(),
        lambda: adapter.enumerate_recordings(),
        lambda: adapter.extract_recording("x"),
        lambda: adapter.find_deleted_recordings(),
        lambda: adapter.recover_recording("x"),
        lambda: adapter.reconstruct_fragments("x"),
        lambda: adapter.decode_metadata(),
        lambda: adapter.validate_recording("x"),
        lambda: adapter.normalize_evidence(),
    ):
        with pytest.raises(AdapterCapabilityNotImplementedError):
            call()


@pytest.mark.parametrize("adapter_cls,_vendor", _RESEARCH_ONLY_ADAPTERS)
def test_supports_returns_false_for_every_capability(
    adapter_cls: type[DVRAdapter], _vendor: str
) -> None:
    from app.adapters.base import AdapterCapability

    adapter = adapter_cls()
    for capability in AdapterCapability:
        assert adapter.supports(capability) is False


@pytest.mark.parametrize("adapter_cls,_vendor", _RESEARCH_ONLY_ADAPTERS)
def test_model_scope_is_never_silently_broad(adapter_cls: type[DVRAdapter], _vendor: str) -> None:
    adapter = adapter_cls()
    scope = adapter.model_scope.lower()
    assert "unknown" in scope or "no specific" in scope
