"""
Hikvision vendor-specific recovery (Phase 26, "Hikvision Integration").

CONTROLLED-EVIDENCE STATUS: the real evidence this project holds
(`~/Documents/24fps-evidence/Hikvision/`) is exported-media evidence only
(Master Specification Section 9, acquisition Path 1) -- three standalone
clips, each a complete, non-fragmented recording. There is no raw HDD/
filesystem image, no HIKBTREE recording index, and no deletion-marker
structure available to search for a deleted-but-referenced recording (that
would require Level 2+ raw-filesystem parsing, which
`app.adapters.hikvision.detector.detect_hikvision_structure`/`__init__`
explicitly documents as NOT implemented).

`find_deleted_hikvision_recordings` below therefore always reports
`RecoveryStatus.UNSUPPORTED` with the explicit
`not_supported_for_exported_media` reason (Phase 26 task scope, section
13) -- never a fabricated deleted-recording recovery, and never silently
reused CP Plus's own (differently-reasoned) "no index found" statement,
since the underlying reason genuinely differs: CP Plus's ADIT-v1 container
was analyzed and found to carry no index at all; Hikvision's export files
were never expected to carry a recording index in the first place -- they
are single already-exported clips, not a multi-recording store.

No "damaged-segment recovery" layer is implemented here either: unlike CP
Plus's proprietary CPAV record framing (byte-level reverse-engineered by
this project), the Hikvision export payload is a standard MPEG-2 Program
Stream -- FFmpeg's own demuxer already reports/tolerates minor stream-level
issues during `app.media.decoder.remux_container_to_mp4` (surfaced
as extraction warnings/`extraction_status="partial"`), and this project has
not implemented independent PS-packet-level carving/reconstruction beyond
what FFmpeg itself already does. Claiming a separate "recovery" capability
on top of that would overstate what is actually implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.recovery import RecoveryStatus

#: The exact, literal capability-status phrase Phase 26 task scope, section
#: 13 requires when deleted-recording recovery is unavailable for exported
#: media (distinct from CP Plus's own `DELETED_RECOVERY_NOT_VALIDATED_
#: STATEMENT` -- see this module's docstring for why the reasons differ).
HIKVISION_RECOVERY_NOT_SUPPORTED_FOR_EXPORTED_MEDIA = "not_supported_for_exported_media"

_NO_INDEX_REASON = (
    f"{HIKVISION_RECOVERY_NOT_SUPPORTED_FOR_EXPORTED_MEDIA}: this evidence is an already-"
    "exported Hikvision clip (Master Specification Section 9, acquisition Path 1), not a raw "
    "HDD/filesystem image -- no HIKBTREE recording index or deletion-marker structure is "
    "present to search. Native Hikvision HDD/filesystem deleted-recording recovery would "
    "require Level 2+ raw-filesystem parsing, which this adapter does not implement (see "
    "app.adapters.hikvision.detector's module docstring)."
)


@dataclass(frozen=True)
class HikvisionDeletedRecordingSearchResult:
    """Outcome of searching for deleted-but-referenced Hikvision recordings."""

    status: RecoveryStatus
    reason: str


def find_deleted_hikvision_recordings() -> HikvisionDeletedRecordingSearchResult:
    """Search for deleted-but-still-referenced recordings.

    Always reports `UNSUPPORTED` for the reason explained in this module's
    docstring -- deterministic, does not depend on the bound evidence's
    contents.

    Returns:
        A `HikvisionDeletedRecordingSearchResult` with `status=UNSUPPORTED`.
    """
    return HikvisionDeletedRecordingSearchResult(
        status=RecoveryStatus.UNSUPPORTED, reason=_NO_INDEX_REASON
    )


_NO_CARVING_REASON = (
    f"{HIKVISION_RECOVERY_NOT_SUPPORTED_FOR_EXPORTED_MEDIA}: no independent, damaged-segment "
    "carving/reconstruction is implemented for Hikvision exported clips beyond whatever FFmpeg's "
    "own demuxer already tolerates/reports during "
    "app.media.decoder.remux_container_to_mp4 (surfaced there as extraction warnings/an "
    "extraction_status of 'partial' or 'failed'). Claiming a separate recovery capability on top "
    "of that would overstate what is actually implemented -- see this module's docstring."
)


@dataclass(frozen=True)
class HikvisionDamagedSegmentRecoveryResult:
    """Outcome of attempting to recover one damaged Hikvision exported clip."""

    status: RecoveryStatus
    reason: str


def recover_damaged_hikvision_segment() -> HikvisionDamagedSegmentRecoveryResult:
    """Attempt independent, damaged-segment recovery for a Hikvision exported clip.

    Always reports `UNSUPPORTED` for the reason explained in this module's
    docstring and `_NO_CARVING_REASON` -- deterministic, does not depend
    on the bound evidence's contents. Real damaged-media tolerance still
    happens, just one layer up: `app.media.decoder.remux_container_to_mp4`
    already surfaces whatever FFmpeg's own demuxer reports/tolerates as
    extraction warnings, which is a distinct, already-implemented
    capability from what this function would claim.

    Returns:
        A `HikvisionDamagedSegmentRecoveryResult` with `status=UNSUPPORTED`.
    """
    return HikvisionDamagedSegmentRecoveryResult(
        status=RecoveryStatus.UNSUPPORTED, reason=_NO_CARVING_REASON
    )
