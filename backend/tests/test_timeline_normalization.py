"""Tests for the one authoritative normalization function
(app/timeline/normalization.py), Phase 11."""

from __future__ import annotations

import datetime

from app.timeline import NormalizationMethod, NormalizationStatus, ReferencePair, TimestampSource
from app.timeline.normalization import apply_verified_offset, normalize

UTC = datetime.UTC


def test_no_original_timestamp_is_unknown():
    result = normalize(None, source=TimestampSource.CPV_BINARY_TIMESTAMP)
    assert result.status == NormalizationStatus.UNKNOWN
    assert result.normalized_timestamp is None
    assert result.original_timestamp is None


def test_naive_original_with_no_source_timezone_is_unknown():
    original = datetime.datetime(2026, 8, 28, 16, 20, 0)
    result = normalize(original, source=TimestampSource.FILENAME_DERIVED)
    assert result.status == NormalizationStatus.UNKNOWN
    assert result.normalized_timestamp is None
    # Original value itself is still carried through, never discarded.
    assert result.original_timestamp == original


def test_invalid_source_timezone_is_unknown_not_a_crash():
    original = datetime.datetime(2026, 8, 28, 16, 20, 0)
    result = normalize(
        original, source=TimestampSource.FILENAME_DERIVED, source_timezone="Not/A_Zone"
    )
    assert result.status == NormalizationStatus.UNKNOWN
    assert "could not be resolved" in result.reason


def test_source_timezone_alone_without_reference_is_unverified():
    original = datetime.datetime(2026, 8, 28, 16, 20, 0)
    result = normalize(
        original,
        source=TimestampSource.FILENAME_DERIVED,
        source_timezone="Asia/Kolkata",
        source_timezone_basis="case device fact sheet",
    )
    assert result.status == NormalizationStatus.UNVERIFIED
    assert result.method == NormalizationMethod.TIMEZONE_CONVERSION
    assert result.normalized_timestamp == datetime.datetime(2026, 8, 28, 10, 50, 0, tzinfo=UTC)
    assert result.offset_seconds is None
    assert result.source_timezone_basis == "case device fact sheet"


def test_verified_with_reference_computes_offset_and_applies_it():
    original = datetime.datetime(2026, 8, 28, 16, 20, 0)
    reference = ReferencePair(
        reference_timestamp=datetime.datetime(2026, 8, 28, 16, 20, 5),
        reference_timezone="Asia/Kolkata",
        reference_source="examiner-recorded reference event",
        reference_basis="examiner observed NVR display next to a synced phone clock",
        method=NormalizationMethod.EXPLICIT_DVR_CLOCK_COMPARISON,
    )
    result = normalize(
        original,
        source=TimestampSource.FILENAME_DERIVED,
        source_timezone="Asia/Kolkata",
        reference=reference,
    )
    assert result.status == NormalizationStatus.VERIFIED
    assert result.offset_seconds == 5.0
    assert result.normalized_timestamp == datetime.datetime(2026, 8, 28, 10, 50, 5, tzinfo=UTC)
    assert result.method == NormalizationMethod.EXPLICIT_DVR_CLOCK_COMPARISON
    assert result.reference is reference


def test_reference_with_already_aware_timestamp_needs_no_reference_timezone():
    original = datetime.datetime(2026, 8, 28, 16, 20, 0)
    reference = ReferencePair(
        reference_timestamp=datetime.datetime(2026, 8, 28, 10, 50, 5, tzinfo=UTC),
        reference_timezone=None,
        reference_source="trusted workstation clock",
        reference_basis="NTP-synced examiner workstation",
    )
    result = normalize(
        original,
        source=TimestampSource.FILENAME_DERIVED,
        source_timezone="Asia/Kolkata",
        reference=reference,
    )
    assert result.status == NormalizationStatus.VERIFIED
    assert result.offset_seconds == 5.0


def test_reference_missing_timezone_falls_back_to_unverified_not_unknown():
    original = datetime.datetime(2026, 8, 28, 16, 20, 0)
    reference = ReferencePair(
        reference_timestamp=datetime.datetime(2026, 8, 28, 16, 20, 5),  # naive
        reference_timezone=None,
        reference_source="examiner note",
        reference_basis="unclear",
    )
    result = normalize(
        original,
        source=TimestampSource.FILENAME_DERIVED,
        source_timezone="Asia/Kolkata",
        reference=reference,
    )
    assert result.status == NormalizationStatus.UNVERIFIED
    assert result.offset_seconds is None
    assert result.normalized_timestamp is not None  # timezone conversion still applied
    assert result.warnings


def test_reference_invalid_timezone_falls_back_to_unverified():
    original = datetime.datetime(2026, 8, 28, 16, 20, 0)
    reference = ReferencePair(
        reference_timestamp=datetime.datetime(2026, 8, 28, 16, 20, 5),
        reference_timezone="Not/A_Zone",
        reference_source="examiner note",
        reference_basis="unclear",
    )
    result = normalize(
        original,
        source=TimestampSource.FILENAME_DERIVED,
        source_timezone="Asia/Kolkata",
        reference=reference,
    )
    assert result.status == NormalizationStatus.UNVERIFIED
    assert result.offset_seconds is None


def test_already_aware_original_ignores_supplied_source_timezone_with_a_warning():
    aware_original = datetime.datetime(2026, 8, 28, 10, 50, 0, tzinfo=UTC)
    result = normalize(
        aware_original,
        source=TimestampSource.FILENAME_DERIVED,
        source_timezone="Asia/Kolkata",
    )
    assert result.status == NormalizationStatus.UNVERIFIED
    assert result.normalized_timestamp == aware_original
    assert result.warnings  # documents that source_timezone was not applied


def test_never_fabricates_a_numeric_confidence_only_status_and_reason():
    original = datetime.datetime(2026, 8, 28, 16, 20, 0)
    result = normalize(
        original, source=TimestampSource.FILENAME_DERIVED, source_timezone="Asia/Kolkata"
    )
    assert not hasattr(result, "confidence")
    assert isinstance(result.reason, str) and result.reason


def test_original_timestamp_is_never_mutated_by_normalization():
    original = datetime.datetime(2026, 8, 28, 16, 20, 0)
    original_copy = datetime.datetime(2026, 8, 28, 16, 20, 0)
    normalize(original, source=TimestampSource.FILENAME_DERIVED, source_timezone="Asia/Kolkata")
    assert original == original_copy


# --- apply_verified_offset (used to carry one anchor's verified offset to a
# second timestamp from the same recording, without re-deriving it) ---


def test_apply_verified_offset_uses_the_given_offset_not_a_fresh_reference_comparison():
    end_original = datetime.datetime(2026, 8, 28, 16, 20, 2)
    reference = ReferencePair(
        reference_timestamp=datetime.datetime(2026, 8, 28, 16, 20, 5),
        reference_timezone="Asia/Kolkata",
        reference_source="examiner-recorded reference event",
        reference_basis="paired against start_original elsewhere",
        method=NormalizationMethod.EXPLICIT_DVR_CLOCK_COMPARISON,
    )
    result = apply_verified_offset(
        end_original,
        source=TimestampSource.FILENAME_DERIVED,
        source_timezone="Asia/Kolkata",
        source_timezone_basis=None,
        offset_seconds=5.0,
        method=NormalizationMethod.EXPLICIT_DVR_CLOCK_COMPARISON,
        reference=reference,
    )
    assert result.status == NormalizationStatus.VERIFIED
    assert result.offset_seconds == 5.0
    # end_original (16:20:02 IST) + 5s offset = 10:50:07 UTC, NOT a fresh
    # (reference - end_original) = 3s offset.
    assert result.normalized_timestamp == datetime.datetime(2026, 8, 28, 10, 50, 7, tzinfo=UTC)


def test_apply_verified_offset_with_none_is_unknown():
    reference = ReferencePair(
        reference_timestamp=datetime.datetime(2026, 8, 28, 16, 20, 5),
        reference_timezone="Asia/Kolkata",
        reference_source="x",
        reference_basis="x",
    )
    result = apply_verified_offset(
        None,
        source=TimestampSource.FILENAME_DERIVED,
        source_timezone="Asia/Kolkata",
        source_timezone_basis=None,
        offset_seconds=5.0,
        method=NormalizationMethod.EXPLICIT_DVR_CLOCK_COMPARISON,
        reference=reference,
    )
    assert result.status == NormalizationStatus.UNKNOWN
