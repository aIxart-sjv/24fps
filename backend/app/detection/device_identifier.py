"""
Device / vendor identification.
Master Specification Section 13 ("Device Identification").

Without a registered vendor-signature database — that is Phase 7+
vendor-adapter territory — this module cannot determine vendor/model/
firmware for arbitrary evidence, and it must not guess (Section 76, rule
6: "Unknown information is not guessed."). It combines explicit,
examiner-declared evidence metadata with what `filesystem_detector`
determined about the container/storage structure into one normalized
`DeviceIdentificationResult`. `vendor`/`model`/`firmware` stay explicitly
`None` unless a genuinely deterministic source becomes available in a
later phase; this module deliberately never infers them from a filename
or a free-text label.
"""

from __future__ import annotations

from app.detection.filesystem_detector import StorageDetectionResult
from app.schemas.device import DeviceIdentificationResult, IdentificationStatus

# Deterministic, explicit classification only — never a vendor/model guess.
_SOURCE_TYPE_DEVICE_TYPE: dict[str, str] = {
    "native_export": "export",
    "raw_dd": "storage_media",
    "direct_storage": "storage_media",
    "e01": "storage_media",
    "forensic_image": "storage_media",
}

# Confidence tiers, each tied to a specific, documented reason a value was
# accepted — never an arbitrary number:
#   1.0  a container/format signature was independently verified
#        (e.g. the EWF/E01 magic bytes, already checked by pyewf)
#   0.6  the examiner's declared source_type is the only basis — plausible,
#        but not independently corroborated (RAW/DD has no header to check)
#   0.4  a filesystem/partition-table signature was found, but it doesn't
#        corroborate (or contradicts) the declared source_type
#   0.0  nothing determined at all
CONFIDENCE_VERIFIED_SIGNATURE = 1.0
CONFIDENCE_EXPLICIT_UNCORROBORATED = 0.6
CONFIDENCE_STRUCTURAL_SIGNAL_ONLY = 0.4
CONFIDENCE_NONE = 0.0


def build_identification_result(
    *,
    source_type: str,
    storage_detection: StorageDetectionResult | None,
    open_warning: str | None = None,
) -> DeviceIdentificationResult:
    """Combine declared evidence metadata and storage detection into one result.

    Args:
        source_type: The evidence's declared `source_type`.
        storage_detection: The result of `detect_storage_structure`, or
            `None` if the evidence source could not be opened as a
            byte-addressable container (e.g. a directory-based export).
        open_warning: A human-readable explanation to attach when
            `storage_detection` is `None`.

    Returns:
        A normalized `DeviceIdentificationResult`. Always succeeds —
        degraded input produces a lower-confidence/`UNKNOWN` result, never
        an exception.
    """
    warnings: list[str] = [open_warning] if open_warning else []
    device_type = _SOURCE_TYPE_DEVICE_TYPE.get(source_type)

    if storage_detection is None:
        has_declaration = device_type is not None
        return DeviceIdentificationResult(
            status=(
                IdentificationStatus.PARTIAL if has_declaration else IdentificationStatus.UNKNOWN
            ),
            device_type=device_type,
            identification_method="explicit_metadata" if has_declaration else "none",
            confidence=CONFIDENCE_EXPLICIT_UNCORROBORATED if has_declaration else CONFIDENCE_NONE,
            warnings=warnings,
            supporting_evidence=(
                [f"device_type derived from declared source_type={source_type!r}"]
                if has_declaration
                else []
            ),
            parser_selection_hints=[],
        )

    supporting_evidence = list(storage_detection.supporting_evidence)
    if device_type is not None:
        supporting_evidence.append(f"device_type derived from declared source_type={source_type!r}")

    parser_selection_hints = [storage_detection.storage_format]
    if storage_detection.filesystem_type:
        parser_selection_hints.append(storage_detection.filesystem_type)
    for partition in storage_detection.partitions:
        if partition.filesystem_type and partition.filesystem_type not in parser_selection_hints:
            parser_selection_hints.append(partition.filesystem_type)

    identification_method, confidence = _determine_confidence(source_type, storage_detection)

    if confidence >= CONFIDENCE_VERIFIED_SIGNATURE:
        status = IdentificationStatus.IDENTIFIED
    elif confidence > CONFIDENCE_NONE:
        status = IdentificationStatus.PARTIAL
    else:
        status = IdentificationStatus.UNKNOWN

    return DeviceIdentificationResult(
        status=status,
        device_type=device_type,
        storage_format=storage_detection.storage_format,
        filesystem_type=storage_detection.filesystem_type,
        sector_size=storage_detection.sector_size,
        capacity=storage_detection.capacity,
        identification_method=identification_method,
        confidence=confidence,
        warnings=warnings,
        supporting_evidence=supporting_evidence,
        parser_selection_hints=parser_selection_hints,
    )


def _determine_confidence(
    source_type: str, storage_detection: StorageDetectionResult
) -> tuple[str, float]:
    """Return (identification_method, confidence) for a successfully opened container."""
    if storage_detection.storage_format == "e01":
        # The EWF/E01 magic signature was already independently verified by
        # pyewf before this reader could even be opened (see
        # app.acquisition.e01_handler.E01Reader) — this is not this
        # module's own check, it is trusting a signature already verified
        # upstream.
        return "container_signature", CONFIDENCE_VERIFIED_SIGNATURE

    if storage_detection.filesystem_type is not None or storage_detection.partitions:
        # A concrete filesystem/partition-table signature was found. This is
        # independently verified structural evidence, but it says nothing
        # about vendor/model, so it does not reach full confidence.
        return "filesystem_signature", CONFIDENCE_STRUCTURAL_SIGNAL_ONLY

    if source_type in _SOURCE_TYPE_DEVICE_TYPE:
        # Only the examiner's declaration backs this — RAW/DD carries no
        # header to independently verify against.
        return "explicit_metadata", CONFIDENCE_EXPLICIT_UNCORROBORATED

    return "none", CONFIDENCE_NONE
