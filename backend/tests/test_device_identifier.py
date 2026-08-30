"""Tests for app.detection.device_identifier.build_identification_result."""

from __future__ import annotations

from app.detection.device_identifier import (
    CONFIDENCE_EXPLICIT_UNCORROBORATED,
    CONFIDENCE_NONE,
    CONFIDENCE_STRUCTURAL_SIGNAL_ONLY,
    CONFIDENCE_VERIFIED_SIGNATURE,
    build_identification_result,
)
from app.detection.filesystem_detector import PartitionDetectionResult, StorageDetectionResult
from app.schemas.device import IdentificationStatus


def test_no_storage_detection_and_no_source_type_is_unknown():
    result = build_identification_result(
        source_type="", storage_detection=None, open_warning="could not open"
    )
    assert result.status == IdentificationStatus.UNKNOWN
    assert result.confidence == CONFIDENCE_NONE
    assert result.identification_method == "none"
    assert result.device_type is None
    assert "could not open" in result.warnings


def test_no_storage_detection_but_known_source_type_is_partial():
    result = build_identification_result(
        source_type="native_export", storage_detection=None, open_warning="is a directory"
    )
    assert result.status == IdentificationStatus.PARTIAL
    assert result.confidence == CONFIDENCE_EXPLICIT_UNCORROBORATED
    assert result.identification_method == "explicit_metadata"
    assert result.device_type == "export"
    assert "is a directory" in result.warnings


def test_e01_container_format_is_identified_with_full_confidence():
    detection = StorageDetectionResult(
        storage_format="e01",
        sector_size=512,
        capacity=4096,
        filesystem_type=None,
    )
    result = build_identification_result(source_type="e01", storage_detection=detection)
    assert result.status == IdentificationStatus.IDENTIFIED
    assert result.confidence == CONFIDENCE_VERIFIED_SIGNATURE
    assert result.identification_method == "container_signature"
    assert result.storage_format == "e01"
    assert "e01" in result.parser_selection_hints


def test_raw_dd_with_no_filesystem_signal_is_explicit_metadata_only():
    detection = StorageDetectionResult(
        storage_format="raw_dd",
        sector_size=512,
        capacity=4096,
        filesystem_type=None,
    )
    result = build_identification_result(source_type="raw_dd", storage_detection=detection)
    assert result.status == IdentificationStatus.PARTIAL
    assert result.confidence == CONFIDENCE_EXPLICIT_UNCORROBORATED
    assert result.identification_method == "explicit_metadata"
    assert result.device_type == "storage_media"


def test_filesystem_signature_found_yields_structural_confidence():
    detection = StorageDetectionResult(
        storage_format="raw_dd",
        sector_size=512,
        capacity=4096,
        filesystem_type="ext2_3_4",
    )
    result = build_identification_result(source_type="raw_dd", storage_detection=detection)
    assert result.status == IdentificationStatus.PARTIAL
    assert result.confidence == CONFIDENCE_STRUCTURAL_SIGNAL_ONLY
    assert result.identification_method == "filesystem_signature"
    assert result.filesystem_type == "ext2_3_4"
    assert "ext2_3_4" in result.parser_selection_hints


def test_partition_filesystem_types_flow_into_parser_selection_hints():
    detection = StorageDetectionResult(
        storage_format="raw_dd",
        sector_size=512,
        capacity=4096,
        filesystem_type=None,
        partitions=[
            PartitionDetectionResult(
                index=0,
                partition_type=0x83,
                start_sector=2048,
                sector_count=100,
                filesystem_type="fat32",
            ),
            PartitionDetectionResult(
                index=1,
                partition_type=0x07,
                start_sector=3000,
                sector_count=100,
                filesystem_type=None,
            ),
        ],
    )
    result = build_identification_result(source_type="raw_dd", storage_detection=detection)
    assert "fat32" in result.parser_selection_hints
    assert result.identification_method == "filesystem_signature"


def test_unrecognized_source_type_with_no_signal_is_unknown():
    detection = StorageDetectionResult(
        storage_format="file", sector_size=512, capacity=10, filesystem_type=None
    )
    result = build_identification_result(source_type="video_file", storage_detection=detection)
    assert result.status == IdentificationStatus.UNKNOWN
    assert result.confidence == CONFIDENCE_NONE
    assert result.identification_method == "none"


def test_vendor_model_firmware_are_never_fabricated():
    """Nothing in this module has a legitimate source for vendor/model/firmware yet."""
    detection = StorageDetectionResult(
        storage_format="e01", sector_size=512, capacity=4096, filesystem_type="ntfs"
    )
    result = build_identification_result(source_type="e01", storage_detection=detection)
    assert result.vendor is None
    assert result.model is None
    assert result.firmware is None
    assert result.serial_number is None


def test_confidence_is_always_within_bounds():
    for storage_format in ("e01", "raw_dd", "file"):
        detection = StorageDetectionResult(
            storage_format=storage_format, sector_size=512, capacity=1, filesystem_type=None
        )
        result = build_identification_result(
            source_type=storage_format, storage_detection=detection
        )
        assert 0.0 <= result.confidence <= 1.0
