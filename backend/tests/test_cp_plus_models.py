"""Tests for CP Plus normalized-output mapping (app/adapters/cp_plus/models.py).

Master Specification Section 9 ("Normalized Output"): CP Plus results must
map onto the existing common `Recording` model rather than a CP Plus-only
downstream shape.
"""

from __future__ import annotations

from sqlalchemy import inspect as sa_inspect

from app.adapters.cp_plus.models import (
    CPPlusParseStatus,
    CPPlusRecordingRecord,
    to_recording_fields,
)
from app.models.recording import Recording


def _sample_record() -> CPPlusRecordingRecord:
    return CPPlusRecordingRecord(
        recording_id="CPPLUS-UNVALIDATED-0001",
        camera_id=None,
        channel=None,
        start_original=None,
        end_original=None,
        duration_ms=None,
        recording_type=None,
        source_evidence_id="E001",
        source_region="header",
        source_offset=0,
        status=CPPlusParseStatus.UNSUPPORTED,
        parser_version="0.1.0-unvalidated",
        confidence=0.0,
    )


def test_to_recording_fields_keys_match_recording_model_exactly():
    """Every key in the mapping must be a real, mutable Recording column — no drift."""
    mapped_keys = set(to_recording_fields(_sample_record()).keys())
    recording_columns = {column.key for column in sa_inspect(Recording).columns}
    identity_columns = {"id", "evidence_id"}
    assert mapped_keys == recording_columns - identity_columns


def test_to_recording_fields_never_fabricates_unavailable_values():
    fields = to_recording_fields(_sample_record())
    # Nothing the source evidence didn't actually provide may be guessed.
    for key in (
        "codec",
        "container",
        "width",
        "height",
        "fps",
        "recovery_status",
        "recovery_method",
    ):
        assert fields[key] is None


def test_to_recording_fields_preserves_recording_id_and_confidence():
    fields = to_recording_fields(_sample_record())
    assert fields["recording_id"] == "CPPLUS-UNVALIDATED-0001"
    assert fields["confidence"] == 0.0
    assert fields["source_location"] == "header@offset=0"
