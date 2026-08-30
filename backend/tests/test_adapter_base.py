"""Tests for the DVRAdapter base contract and AdapterCapability (app/adapters/base.py)."""

from __future__ import annotations

import pytest

from app.adapters.base import (
    AdapterCapability,
    AdapterCapabilityNotImplementedError,
    AdapterResult,
    DVRAdapter,
)
from tests.dummy_adapter import DummyAdapter


def test_dvr_adapter_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        DVRAdapter()  # type: ignore[abstract]


def test_dummy_adapter_satisfies_the_contract():
    adapter = DummyAdapter(vendor="CP Plus")
    assert isinstance(adapter, DVRAdapter)
    assert adapter.vendor == "CP Plus"
    assert adapter.model_pattern == ".*"
    assert adapter.firmware_pattern is None
    assert adapter.capabilities == frozenset()
    assert adapter.adapter_version


def test_supports_reflects_declared_capabilities():
    adapter = DummyAdapter(
        vendor="CP Plus",
        capabilities=frozenset({AdapterCapability.DEVICE_IDENTIFICATION}),
    )
    assert adapter.supports(AdapterCapability.DEVICE_IDENTIFICATION) is True
    assert adapter.supports(AdapterCapability.RECOVERY) is False


@pytest.mark.parametrize(
    "method_name,args",
    [
        ("identify", ()),
        ("detect_capabilities", ()),
        ("inspect_storage", ()),
        ("parse_filesystem", ()),
        ("parse_metadata", ()),
        ("enumerate_recordings", ()),
        ("extract_recording", ("REC-1",)),
        ("find_deleted_recordings", ()),
        ("recover_recording", ("REC-1",)),
        ("reconstruct_fragments", ("REC-1",)),
        ("decode_metadata", ()),
        ("validate_recording", ("REC-1",)),
        ("normalize_evidence", ()),
    ],
)
def test_every_unimplemented_operation_raises_the_typed_error(method_name: str, args: tuple):
    """No DVRAdapter operation may silently succeed or return a fabricated result
    when the concrete adapter has not implemented it."""
    adapter = DummyAdapter(vendor="CP Plus")
    method = getattr(adapter, method_name)
    with pytest.raises(AdapterCapabilityNotImplementedError, match="CP Plus"):
        method(*args)


def test_not_implemented_error_names_the_operation_and_adapter():
    adapter = DummyAdapter(vendor="Hikvision", adapter_version="1.2.3")
    with pytest.raises(AdapterCapabilityNotImplementedError) as exc_info:
        adapter.normalize_evidence()
    message = str(exc_info.value)
    assert "Hikvision" in message
    assert "1.2.3" in message
    assert "normalize_evidence" in message


def test_adapter_capability_values_are_stable_strings():
    """Capability values are serialization-stable identifiers, not just labels."""
    assert AdapterCapability.DEVICE_IDENTIFICATION.value == "device_identification"
    assert AdapterCapability.RECOVERY.value == "recovery"


def test_adapter_result_defaults_are_empty_not_fabricated():
    result = AdapterResult(
        vendor="CP Plus",
        model=None,
        firmware=None,
        detected_format=None,
        capability_set=frozenset(),
    )
    assert result.recordings == []
    assert result.metadata == {}
    assert result.recovery_candidates == []
    assert result.warnings == []
    assert result.confidence == 0.0
