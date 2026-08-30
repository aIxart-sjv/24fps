"""Tests for app/adapters/factory.py (Phase 19): the fully-populated
default registry, and -- most importantly -- proof that CP Plus
selection is unaffected by registering seven additional vendor adapters
alongside it (task Phase 19 scope: "Verify that: AdapterRegistry still
selects CP Plus correctly... new vendor adapters register
deterministically... registry listing accurately reports support
levels/capabilities").
"""

from __future__ import annotations

from app.adapters import AdapterCapability, AdapterSelectionStatus, SupportLevel
from app.adapters.factory import build_default_registry
from app.schemas.device import DeviceIdentificationResult, IdentificationStatus


def _result(**overrides: object) -> DeviceIdentificationResult:
    defaults: dict[str, object] = {
        "status": IdentificationStatus.PARTIAL,
        "identification_method": "test_fixture",
        "confidence": 0.5,
    }
    defaults.update(overrides)
    return DeviceIdentificationResult(**defaults)  # type: ignore[arg-type]


def test_default_registry_registers_all_eight_named_oems() -> None:
    registry = build_default_registry()
    vendors = {adapter.vendor for adapter in registry.list_adapters()}
    assert vendors == {
        "CP Plus",
        "Dahua Technology",
        "Honeywell Security",
        "Hikvision",
        "TP-Link",
        "Godrej",
        "Uniview",
        "Matrix",
    }
    assert len(registry.list_adapters()) == 8


def test_registering_seven_more_vendors_does_not_raise() -> None:
    """Registration must be deterministic and collision-free across all
    eight vendors' (vendor, model_pattern, firmware_pattern) identities."""
    registry = build_default_registry()  # would raise ValueError on any collision
    assert len(registry.list_adapters()) == 8


def test_cp_plus_still_selects_correctly_among_all_vendors() -> None:
    registry = build_default_registry()
    result = _result(status=IdentificationStatus.IDENTIFIED, vendor="CP Plus")
    selection = registry.select_adapter(result)
    assert selection.status == AdapterSelectionStatus.SELECTED
    assert selection.adapter is not None
    assert selection.adapter.vendor == "CP Plus"
    assert selection.adapter.support_level == SupportLevel.LEVEL_4_VALIDATED


def test_each_vendor_selects_itself_and_no_other() -> None:
    registry = build_default_registry()
    for vendor in (
        "CP Plus",
        "Dahua Technology",
        "Honeywell Security",
        "Hikvision",
        "TP-Link",
        "Godrej",
        "Uniview",
        "Matrix",
    ):
        result = _result(status=IdentificationStatus.IDENTIFIED, vendor=vendor)
        selection = registry.select_adapter(result)
        assert selection.status == AdapterSelectionStatus.SELECTED
        assert selection.adapter is not None
        assert selection.adapter.vendor == vendor


def test_unknown_vendor_never_matches_any_registered_adapter() -> None:
    registry = build_default_registry()
    result = _result(status=IdentificationStatus.IDENTIFIED, vendor="Totally Unknown Brand")
    selection = registry.select_adapter(result)
    assert selection.status == AdapterSelectionStatus.UNSUPPORTED
    assert selection.adapter is None


def test_unknown_identification_status_never_guesses_a_vendor() -> None:
    registry = build_default_registry()
    result = _result(status=IdentificationStatus.UNKNOWN)
    selection = registry.select_adapter(result)
    assert selection.status == AdapterSelectionStatus.UNKNOWN_VENDOR
    assert selection.adapter is None


# ---- Support matrix accuracy -------------------------------------------


def test_support_matrix_lists_every_registered_adapter() -> None:
    registry = build_default_registry()
    matrix = registry.support_matrix()
    assert len(matrix) == 8
    assert {entry.vendor for entry in matrix} == {
        adapter.vendor for adapter in registry.list_adapters()
    }


def test_support_matrix_only_cp_plus_reaches_level_4() -> None:
    registry = build_default_registry()
    matrix = registry.support_matrix()
    level_4_vendors = [
        e.vendor for e in matrix if e.support_level == SupportLevel.LEVEL_4_VALIDATED
    ]
    assert level_4_vendors == ["CP Plus"]


def test_support_matrix_only_dahua_and_hikvision_reach_level_1() -> None:
    registry = build_default_registry()
    matrix = registry.support_matrix()
    level_1_vendors = {
        e.vendor for e in matrix if e.support_level == SupportLevel.LEVEL_1_DETECTION
    }
    assert level_1_vendors == {"Dahua Technology", "Hikvision"}


def test_support_matrix_five_vendors_are_research_only() -> None:
    registry = build_default_registry()
    matrix = registry.support_matrix()
    level_0_vendors = {
        e.vendor for e in matrix if e.support_level == SupportLevel.LEVEL_0_RESEARCH_ONLY
    }
    assert level_0_vendors == {
        "Honeywell Security",
        "TP-Link",
        "Godrej",
        "Uniview",
        "Matrix",
    }


def test_support_matrix_never_claims_recording_extraction_except_cp_plus() -> None:
    """Task Phase 19 scope: "Do not claim MEDIA_EXTRACTION if no
    validated extraction path exists." Verified across the whole
    registry, not just per-adapter."""
    registry = build_default_registry()
    for entry in registry.support_matrix():
        if AdapterCapability.RECORDING_EXTRACTION in entry.capabilities:
            assert entry.vendor == "CP Plus"


def test_support_matrix_never_claims_recovery_except_cp_plus() -> None:
    """Task Phase 19 scope: "Do not claim RECOVERY merely because a
    generic recovery framework exists.\" """
    registry = build_default_registry()
    for entry in registry.support_matrix():
        if AdapterCapability.RECOVERY in entry.capabilities:
            assert entry.vendor == "CP Plus"


def test_support_matrix_research_only_vendors_have_zero_capabilities() -> None:
    registry = build_default_registry()
    for entry in registry.support_matrix():
        if entry.support_level == SupportLevel.LEVEL_0_RESEARCH_ONLY:
            assert entry.capabilities == frozenset()


def test_support_matrix_every_entry_has_nonempty_limitations_or_is_fully_validated() -> None:
    """Every adapter below LEVEL_4 must document at least one limitation
    -- support must never look silently complete."""
    registry = build_default_registry()
    for entry in registry.support_matrix():
        if entry.support_level != SupportLevel.LEVEL_4_VALIDATED:
            assert len(entry.limitations) > 0


def test_support_matrix_every_entry_has_nonempty_evidence_basis() -> None:
    registry = build_default_registry()
    for entry in registry.support_matrix():
        assert len(entry.evidence_basis) > 0


def test_build_default_registry_returns_a_fresh_instance_each_call() -> None:
    registry_a = build_default_registry()
    registry_b = build_default_registry()
    assert registry_a is not registry_b
    assert registry_a.list_adapters()[0] is not registry_b.list_adapters()[0]
