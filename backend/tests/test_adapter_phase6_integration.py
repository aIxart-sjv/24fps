"""Tests proving the Phase 6 -> Phase 7 handoff: identify_evidence() output
feeds directly into AdapterRegistry.select_adapter() with no translation layer.
"""

from __future__ import annotations

from pathlib import Path

from app.adapters import AdapterRegistry, AdapterSelectionStatus
from app.detection import identify_evidence
from app.schemas.device import DeviceIdentificationResult, IdentificationStatus
from tests.dummy_adapter import DummyAdapter


def test_real_identify_evidence_output_is_directly_selectable(tmp_path: Path):
    """`identify_evidence`'s return value needs no adaptation to reach `select_adapter`."""
    path = tmp_path / "image.dd"
    path.write_bytes(b"\x00" * 4096)

    result = identify_evidence("raw_dd", path)
    assert isinstance(result, DeviceIdentificationResult)
    # A bare RAW/DD file with no filesystem signature reaches Phase 6's
    # PARTIAL status (explicit source_type only) — not UNKNOWN — so
    # selection does proceed to matching below.
    assert result.status == IdentificationStatus.PARTIAL
    assert result.vendor is None  # Phase 6 never determines a real vendor today

    registry = AdapterRegistry()
    registry.register_adapter(DummyAdapter(vendor="CP Plus"))

    selection = registry.select_adapter(result)

    # Matching was attempted (identification wasn't UNKNOWN/UNSUPPORTED),
    # but with no vendor in the result nothing can match — UNSUPPORTED,
    # never a silently-chosen generic adapter. This proves selection
    # consumes the real Phase 6 object end-to-end, not that a match
    # happens to occur.
    assert selection.status == AdapterSelectionStatus.UNSUPPORTED
    assert selection.adapter is None
    assert len(selection.attempts) == 1
    assert selection.attempts[0].matched is False


def test_unsupported_e01_identification_flows_through_to_unknown_vendor_selection(
    tmp_path: Path,
):
    """A Phase 6 UNSUPPORTED result (e.g. bad E01 signature) must also short-circuit selection."""
    fake_e01 = tmp_path / "fake.E01"
    fake_e01.write_bytes(b"not a real EWF file" * 20)

    result = identify_evidence("e01", fake_e01)

    registry = AdapterRegistry()
    registry.register_adapter(DummyAdapter(vendor="CP Plus"))

    selection = registry.select_adapter(result)

    assert selection.status == AdapterSelectionStatus.UNKNOWN_VENDOR
    assert selection.adapter is None


def test_detection_package_does_not_import_adapters():
    """Phase 6 must stay independent of the vendor-adapter framework (no reverse coupling).

    A static source scan, rather than runtime introspection: reliably
    catches any `import app.adapters...` / `from app.adapters ...` line
    without depending on how names happen to get bound at runtime.
    """
    detection_dir = Path(__file__).resolve().parent.parent / "app" / "detection"
    source_files = sorted(detection_dir.glob("*.py"))
    assert source_files, "expected app/detection/*.py to exist"

    for source_file in source_files:
        text = source_file.read_text(encoding="utf-8")
        assert "app.adapters" not in text, (
            f"{source_file.relative_to(detection_dir.parent.parent)} references "
            "app.adapters — Phase 6 must not depend on the Phase 7 adapter framework"
        )
