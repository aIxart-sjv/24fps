"""
Device / format identification (Phase 6).
Master Specification Section 13 ("Device Identification"), Section 14
("Filesystem Detection"), Section 89 (Phase 6: "Device/format
identification").

Identifies what can be reliably determined about already-registered
evidence — container format, storage/filesystem structure, and (only
where a genuinely deterministic source exists) device-adjacent facts —
without any knowledge of a specific vendor's proprietary recording
format. That knowledge belongs to Phase 7 vendor adapters, layered on top
of this module's output: `identify_evidence` never selects, references,
or imports a vendor adapter, and `DeviceIdentificationResult` is the
normalized handoff `select_adapter(...)` is expected to consume once
Phase 7 exists.
"""

from __future__ import annotations

from pathlib import Path

from app.acquisition import E01FormatError, E01UnavailableError, open_reader
from app.detection.device_identifier import build_identification_result
from app.detection.filesystem_detector import detect_storage_structure
from app.schemas.device import DeviceIdentificationResult, IdentificationStatus

__all__ = ["identify_evidence"]


def identify_evidence(source_type: str, source_path: Path) -> DeviceIdentificationResult:
    """Run Phase 6 identification against a registered evidence source.

    Strictly read-only: opens the source only through the Phase 5 reader
    abstraction (never writes, never touches permissions/timestamps), and
    inspects only a bounded header window per
    `app.detection.filesystem_detector`, not the whole container.

    Always returns a structured result — a container/format problem in the
    evidence itself becomes part of the result (`status`, `warnings`),
    never an uncaught exception (Master Specification Section 55:
    "flag unsupported formats instead of inventing a structure").

    Args:
        source_type: The evidence's declared `source_type`.
        source_path: Resolved path to the evidence source.

    Returns:
        A normalized `DeviceIdentificationResult`.
    """
    if source_path.is_dir():
        return build_identification_result(
            source_type=source_type,
            storage_detection=None,
            open_warning=(
                "source is a directory; byte-level format/filesystem identification does not "
                "apply to directory-based exports"
            ),
        )

    try:
        reader = open_reader(source_type, source_path)
    except E01UnavailableError as exc:
        return DeviceIdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            storage_format=source_type,
            identification_method="explicit_metadata",
            confidence=0.0,
            warnings=[str(exc)],
        )
    except E01FormatError as exc:
        return DeviceIdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            storage_format=source_type,
            identification_method="container_signature",
            confidence=0.0,
            warnings=[str(exc)],
        )
    except (ValueError, OSError) as exc:
        return build_identification_result(
            source_type=source_type,
            storage_detection=None,
            open_warning=f"unable to open evidence source: {exc}",
        )

    try:
        storage_detection = detect_storage_structure(reader)
    finally:
        reader.close()

    return build_identification_result(source_type=source_type, storage_detection=storage_detection)
