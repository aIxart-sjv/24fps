"""Tests for AdapterRegistry: registration, matching, and selection (app/adapters/registry.py)."""

from __future__ import annotations

import pytest

from app.adapters import (
    AdapterCapability,
    AdapterRegistry,
    AdapterSelectionStatus,
    MatchStrength,
)
from app.schemas.device import DeviceIdentificationResult, IdentificationStatus
from tests.dummy_adapter import DummyAdapter


def _result(**overrides) -> DeviceIdentificationResult:
    """Build a DeviceIdentificationResult as Phase 6 might hand to selection.

    Phase 6 never actually populates vendor/model/firmware today (no
    vendor-signature knowledge exists yet) — these tests construct
    hypothetical results with those fields set to prove the matching
    logic itself, independent of Phase 6's current real-world output.
    """
    defaults = {
        "status": IdentificationStatus.PARTIAL,
        "identification_method": "test_fixture",
        "confidence": 0.5,
    }
    defaults.update(overrides)
    return DeviceIdentificationResult(**defaults)


@pytest.fixture
def registry() -> AdapterRegistry:
    return AdapterRegistry()


# --- registration ---


def test_register_and_list_adapters(registry: AdapterRegistry):
    adapter = DummyAdapter(vendor="CP Plus")
    registry.register_adapter(adapter)
    assert registry.list_adapters() == [adapter]


def test_registration_order_is_preserved(registry: AdapterRegistry):
    first = DummyAdapter(vendor="CP Plus")
    second = DummyAdapter(vendor="Hikvision")
    registry.register_adapter(first)
    registry.register_adapter(second)
    assert registry.list_adapters() == [first, second]


def test_duplicate_identity_registration_is_rejected(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*"))


def test_duplicate_check_is_case_insensitive_on_vendor(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern="X"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register_adapter(DummyAdapter(vendor="cp plus", model_pattern="X"))


def test_same_vendor_different_model_pattern_is_allowed(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*"))
    registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern="DVR-8CH.*"))
    assert len(registry.list_adapters()) == 2


def test_invalid_model_pattern_is_rejected_at_registration(registry: AdapterRegistry):
    adapter = DummyAdapter(vendor="CP Plus", model_pattern="(unclosed[")
    with pytest.raises(ValueError, match="invalid model_pattern"):
        registry.register_adapter(adapter)


def test_invalid_firmware_pattern_is_rejected_at_registration(registry: AdapterRegistry):
    adapter = DummyAdapter(vendor="CP Plus", firmware_pattern="(unclosed[")
    with pytest.raises(ValueError, match="invalid firmware_pattern"):
        registry.register_adapter(adapter)


# --- matching / find_matches explainability ---


def test_find_matches_explains_vendor_mismatch(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus"))
    attempts = registry.find_matches(_result(vendor="Hikvision"))
    assert len(attempts) == 1
    assert attempts[0].matched is False
    assert "does not match" in attempts[0].reason


def test_find_matches_explains_model_mismatch(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*"))
    attempts = registry.find_matches(_result(vendor="CP Plus", model="NVR-16CH-X1"))
    assert attempts[0].matched is False
    assert "model" in attempts[0].reason


def test_find_matches_explains_firmware_mismatch(registry: AdapterRegistry):
    registry.register_adapter(
        DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*", firmware_pattern=r"1\.0\..*")
    )
    attempts = registry.find_matches(
        _result(vendor="CP Plus", model="DVR-4CH-X1", firmware="2.0.5")
    )
    assert attempts[0].matched is False
    assert "firmware" in attempts[0].reason


def test_no_vendor_in_result_never_matches(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus"))
    attempts = registry.find_matches(_result())
    assert attempts[0].matched is False
    assert "no vendor" in attempts[0].reason


# --- selection: strength / priority ---


def test_exact_vendor_model_firmware_match_has_highest_strength(registry: AdapterRegistry):
    registry.register_adapter(
        DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*", firmware_pattern=r"1\.0\..*")
    )
    result = registry.select_adapter(
        _result(vendor="CP Plus", model="DVR-4CH-X1", firmware="1.0.5")
    )
    assert result.status == AdapterSelectionStatus.SELECTED
    assert result.attempts[0].strength == MatchStrength.VENDOR_MODEL_AND_FIRMWARE


def test_vendor_and_model_match_without_firmware_confirmation(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*"))
    result = registry.select_adapter(_result(vendor="CP Plus", model="DVR-4CH-X1"))
    assert result.status == AdapterSelectionStatus.SELECTED
    assert result.attempts[0].strength == MatchStrength.VENDOR_AND_MODEL


def test_vendor_only_generic_adapter_matches_as_weakest_tier(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern=".*"))
    result = registry.select_adapter(_result(vendor="CP Plus", model="SomeUnlistedModel"))
    assert result.status == AdapterSelectionStatus.SELECTED
    assert result.attempts[0].strength == MatchStrength.VENDOR_ONLY


def test_specific_model_adapter_is_preferred_over_generic_vendor_adapter(
    registry: AdapterRegistry,
):
    generic = DummyAdapter(vendor="CP Plus", model_pattern=".*")
    specific = DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*")
    registry.register_adapter(generic)
    registry.register_adapter(specific)

    result = registry.select_adapter(_result(vendor="CP Plus", model="DVR-4CH-X1"))

    assert result.status == AdapterSelectionStatus.SELECTED
    assert result.adapter is specific


def test_firmware_confirmed_adapter_preferred_over_model_only_adapter(registry: AdapterRegistry):
    model_only = DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*")
    with_firmware = DummyAdapter(
        vendor="CP Plus", model_pattern="DVR-4CH-X.*", firmware_pattern=r"1\.0\..*"
    )
    registry.register_adapter(model_only)
    registry.register_adapter(with_firmware)

    result = registry.select_adapter(
        _result(vendor="CP Plus", model="DVR-4CH-X1", firmware="1.0.5")
    )

    assert result.adapter is with_firmware


def test_tie_break_is_first_registered(registry: AdapterRegistry):
    # Distinct model_pattern values (so registration itself is valid) that
    # both happen to match the same evidence at the same VENDOR_AND_MODEL
    # strength — a genuine tie.
    first = DummyAdapter(vendor="CP Plus", model_pattern="DVR-4CH.*")
    second = DummyAdapter(vendor="CP Plus", model_pattern=".*4CH-X1")
    registry.register_adapter(first)
    registry.register_adapter(second)

    result = registry.select_adapter(_result(vendor="CP Plus", model="DVR-4CH-X1"))

    assert result.adapter is first


# --- UNKNOWN / UNSUPPORTED behavior ---


def test_unknown_identification_status_never_attempts_matching(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern=".*"))
    result = registry.select_adapter(_result(status=IdentificationStatus.UNKNOWN))
    assert result.status == AdapterSelectionStatus.UNKNOWN_VENDOR
    assert result.adapter is None
    assert result.attempts == []


def test_unsupported_identification_status_never_attempts_matching(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="CP Plus", model_pattern=".*"))
    result = registry.select_adapter(_result(status=IdentificationStatus.UNSUPPORTED))
    assert result.status == AdapterSelectionStatus.UNKNOWN_VENDOR
    assert result.attempts == []


def test_known_vendor_with_no_registered_adapter_is_unsupported(registry: AdapterRegistry):
    registry.register_adapter(DummyAdapter(vendor="Hikvision"))
    result = registry.select_adapter(_result(vendor="CP Plus", model="DVR-4CH-X1"))
    assert result.status == AdapterSelectionStatus.UNSUPPORTED
    assert result.adapter is None
    assert "CP Plus" in result.reason


def test_empty_registry_is_unsupported_not_a_crash(registry: AdapterRegistry):
    result = registry.select_adapter(_result(vendor="CP Plus", model="DVR-4CH-X1"))
    assert result.status == AdapterSelectionStatus.UNSUPPORTED
    assert result.adapter is None


def test_never_falls_back_to_a_generic_adapter_for_a_different_vendor(registry: AdapterRegistry):
    """A registered generic adapter for one vendor must never catch another vendor's evidence."""
    registry.register_adapter(DummyAdapter(vendor="Hikvision", model_pattern=".*"))
    result = registry.select_adapter(_result(vendor="CP Plus", model="DVR-4CH-X1"))
    assert result.status == AdapterSelectionStatus.UNSUPPORTED
    assert result.adapter is None


# --- capability inspection via the registry ---


def test_selected_adapter_capabilities_are_inspectable(registry: AdapterRegistry):
    adapter = DummyAdapter(
        vendor="CP Plus",
        capabilities=frozenset(
            {AdapterCapability.DEVICE_IDENTIFICATION, AdapterCapability.RECORDING_ENUMERATION}
        ),
    )
    registry.register_adapter(adapter)
    result = registry.select_adapter(_result(vendor="CP Plus"))
    assert result.adapter is not None
    assert result.adapter.supports(AdapterCapability.DEVICE_IDENTIFICATION)
    assert not result.adapter.supports(AdapterCapability.RECOVERY)


# --- no vendor parser execution during Phase 7 ---


def test_selection_never_invokes_any_adapter_operation_method(registry: AdapterRegistry):
    """Selecting an adapter must be pure metadata matching — it must never call
    into any of the adapter's Section 16 parsing operations."""
    adapter = DummyAdapter(vendor="CP Plus")
    registry.register_adapter(adapter)

    # None of these are implemented by DummyAdapter; if selection touched any
    # of them, this call would raise AdapterCapabilityNotImplementedError.
    result = registry.select_adapter(_result(vendor="CP Plus"))

    assert result.status == AdapterSelectionStatus.SELECTED
    assert result.adapter is adapter
