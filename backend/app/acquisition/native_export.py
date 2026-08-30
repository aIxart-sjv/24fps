"""
Native-export acquisition path.
Master Specification Section 9 ("Acquisition Backend"), Path 1: "use when
the DVR is functioning and the required evidence is accessible - capture
the exported data plus available vendor metadata/player/logs - register
the export as evidence."

A native export is whatever the DVR/NVR's own export function produced
(recording files, and typically a vendor player and log files alongside
them) copied onto the examiner's workstation. This module intentionally
contains no vendor-specific parsing of that export's contents — identifying
what is actually inside it is Phase 6 (device/format identification) and
Phase 7+ (vendor adapters). Registration here only pins the evidence's
`source_type` and reuses the same root-bound, read-only source validation
every other evidence path already goes through
(`app.utils.paths.resolve_evidence_source_path`).
"""

from __future__ import annotations

from typing import Final

NATIVE_EXPORT_SOURCE_TYPE: Final[str] = "native_export"
