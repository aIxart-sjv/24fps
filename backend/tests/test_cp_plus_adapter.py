"""Tests for CPPlusAdapter (app/adapters/cp_plus/__init__.py).

Phase 8 / Fourth Backend Milestone. Proves the adapter satisfies the
Phase 7 `DVRAdapter` contract, registers/selects correctly through
`AdapterRegistry`, and — end to end, through a real `EvidenceStorageReader`
— honestly reports UNSUPPORTED for evidence that does not match the
validated "ADIT-v1" signature. End-to-end validation against the real
13-file evidence package lives in test_cp_plus_real_evidence_integration.py.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.acquisition.storage_reader import FileBackedReader
from app.adapters import AdapterRegistry, AdapterSelectionStatus, MatchStrength
from app.adapters.base import AdapterCapability
from app.adapters.cp_plus import PARSER_VERSION, CPPlusAdapter
from app.schemas.device import DeviceIdentificationResult, IdentificationStatus

_EXPECTED_CAPABILITIES = frozenset(
    {
        AdapterCapability.FILESYSTEM_DETECTION,
        AdapterCapability.RECORDING_ENUMERATION,
        AdapterCapability.METADATA_EXTRACTION,
        # Phase 9 ("Recording extraction + FFmpeg"): this adapter now
        # genuinely implements `extract_recording` (elementary-stream
        # reconstruction) — see app/adapters/cp_plus/extraction.py.
        AdapterCapability.RECORDING_EXTRACTION,
        # Phase 10 ("Recovery Engine"): this adapter now genuinely
        # implements `recover_recording` (real, validated damaged-recording
        # recovery) and `find_deleted_recordings` (a real, tested, but
        # unvalidated framework path) — see app/adapters/cp_plus/recovery.py.
        AdapterCapability.RECOVERY,
    }
)


def _identification(**overrides) -> DeviceIdentificationResult:
    defaults = {
        "status": IdentificationStatus.PARTIAL,
        "identification_method": "test_fixture",
        "confidence": 0.5,
    }
    defaults.update(overrides)
    return DeviceIdentificationResult(**defaults)


@pytest.fixture
def sample_evidence(tmp_path: Path) -> Path:
    path = tmp_path / "evidence.bin"
    path.write_bytes(os.urandom(8192))
    return path


# --- declarative identity (no evidence needed) ---


def test_vendor_is_cp_plus():
    assert CPPlusAdapter().vendor == "CP Plus"


def test_model_pattern_is_generic():
    assert CPPlusAdapter().model_pattern == ".*"


def test_capabilities_match_what_is_genuinely_implemented():
    """Only capabilities validated against the real ADIT-v1 evidence are claimed.

    TIMESTAMP_EXTRACTION, RECOVERY, DEVICE_IDENTIFICATION, and
    NATIVE_EXPORT_HANDLING are deliberately excluded — see
    app/adapters/cp_plus/__init__.py's `capabilities` property.
    """
    assert CPPlusAdapter().capabilities == _EXPECTED_CAPABILITIES


def test_adapter_version_matches_parser_version():
    assert CPPlusAdapter().adapter_version == PARSER_VERSION


def test_supports_exactly_the_declared_capabilities():
    adapter = CPPlusAdapter()
    for capability in AdapterCapability:
        assert adapter.supports(capability) == (capability in _EXPECTED_CAPABILITIES)


# --- registration / selection through AdapterRegistry ---


def test_cp_plus_adapter_registers_without_error():
    registry = AdapterRegistry()
    registry.register_adapter(CPPlusAdapter())
    assert len(registry.list_adapters()) == 1


def test_cp_plus_adapter_is_selected_for_cp_plus_vendor_identification():
    registry = AdapterRegistry()
    registry.register_adapter(CPPlusAdapter())

    result = registry.select_adapter(_identification(vendor="CP Plus"))

    assert result.status == AdapterSelectionStatus.SELECTED
    assert isinstance(result.adapter, CPPlusAdapter)
    assert result.attempts[0].strength == MatchStrength.VENDOR_ONLY


def test_cp_plus_adapter_is_not_selected_for_a_different_vendor():
    registry = AdapterRegistry()
    registry.register_adapter(CPPlusAdapter())

    result = registry.select_adapter(_identification(vendor="Hikvision"))

    assert result.status == AdapterSelectionStatus.UNSUPPORTED
    assert result.adapter is None


def test_cp_plus_adapter_selection_never_invokes_any_parsing_operation():
    """Selection is pure metadata matching — it must never touch evidence."""
    registry = AdapterRegistry()
    registry.register_adapter(CPPlusAdapter())  # no reader bound

    result = registry.select_adapter(_identification(vendor="CP Plus"))

    assert result.status == AdapterSelectionStatus.SELECTED
    # If selection had invoked any operation method, this would already
    # have raised: the registry-held instance has no bound reader.


# --- reader-bound operations require a reader ---


def test_operations_without_a_bound_reader_raise_a_clear_error():
    adapter = CPPlusAdapter()
    with pytest.raises(ValueError, match="no bound evidence reader"):
        adapter.inspect_storage()


# --- end-to-end: real evidence, honest UNSUPPORTED result ---


def test_inspect_storage_against_real_evidence_is_honest_and_structured(sample_evidence: Path):
    """`sample_evidence` here is random bytes — not the real ADIT-v1 evidence — so
    detection must still honestly report UNSUPPORTED. Declared capabilities
    are a static property and stay populated regardless (see
    test_capabilities_match_what_is_genuinely_implemented)."""
    with FileBackedReader(sample_evidence) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id="E001")
        result = adapter.inspect_storage()

    assert result.vendor == "CP Plus"
    assert result.detected_format is None
    assert result.capability_set == _EXPECTED_CAPABILITIES
    assert result.recordings == []
    assert result.confidence == 0.0
    assert result.parser_version == PARSER_VERSION
    assert any("none matched this evidence's header" in warning for warning in result.warnings)


def test_parse_filesystem_is_an_alias_for_inspect_storage(sample_evidence: Path):
    with FileBackedReader(sample_evidence) as reader:
        adapter = CPPlusAdapter(reader)
        assert adapter.parse_filesystem() == adapter.inspect_storage()


def test_enumerate_recordings_against_real_evidence_returns_no_fabricated_recordings(
    sample_evidence: Path,
):
    with FileBackedReader(sample_evidence) as reader:
        adapter = CPPlusAdapter(reader, source_evidence_id="E001")
        result = adapter.enumerate_recordings()

    assert result.recordings == []
    assert result.parser_version == PARSER_VERSION


def test_normalize_evidence_matches_enumerate_recordings(sample_evidence: Path):
    with FileBackedReader(sample_evidence) as reader:
        adapter = CPPlusAdapter(reader)
        assert adapter.normalize_evidence() == adapter.enumerate_recordings()


def test_capabilities_are_declarative_not_evidence_conditional(sample_evidence: Path):
    """Running operations against evidence that does NOT match must not change
    the declared capability set — it is a static, evidence-independent
    declaration (Master Specification Section 16: identity must be
    determinable without evidence), not something a specific call's
    success/failure can upgrade or downgrade."""
    adapter = CPPlusAdapter()
    before = adapter.capabilities
    with FileBackedReader(sample_evidence) as reader:
        bound = CPPlusAdapter(reader)
        bound.inspect_storage()
        bound.enumerate_recordings()
        bound.normalize_evidence()
        after = bound.capabilities
    assert before == after == _EXPECTED_CAPABILITIES
