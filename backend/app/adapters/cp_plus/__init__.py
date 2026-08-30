"""
CP Plus vendor adapter (Phase 8 / Fourth Backend Milestone: "Implement the
first real parser using controlled test evidence").

CONTROLLED-EVIDENCE STATUS — read before touching `capabilities` below
------------------------------------------------------------------------
A real, controlled CP Plus evidence package (13 `.cpv` files + the vendor
player, SHA-256/MD5 verified) has now been analyzed and used to validate
one container signature, "ADIT-v1" — see
`app.adapters.cp_plus.models`'s module docstring for exactly which
NVR/firmware/camera it came from, and that evidence package's own
`analysis/CPV_ANALYSIS_REPORT.md` for the full byte-level analysis this
implementation is built from.

This adapter now implements real, bounded/streaming parsing for evidence
matching that one signature:
  - registration/selection through `AdapterRegistry` (vendor identity is
    declarative and needs no evidence to determine),
  - bounded-read-safe, signature-based structure detection
    (`app.adapters.cp_plus.detector`),
  - real record-level parsing (`app.adapters.cp_plus.container`) — magic/
    length/footer validation, record-family classification, H.265 NAL
    detection, JSON telemetry extraction, all evidence-driven, and
  - a recording-enumeration contract (`app.adapters.cp_plus.parser`) that
    maps the result onto the common normalized `Recording` shape.

Evidence that does NOT match "ADIT-v1" (including CP Plus evidence from a
different model/firmware/export tool) still honestly reports
UNSUPPORTED/UNKNOWN — this adapter never generalizes past what it actually
validated (docs/PROJECT_RULES.md rule 6; Master Specification Section 17:
"Never report 'CP Plus fully supported' if only one model is tested").

SUPPORTED: "ADIT-v1" container structure only, as found in the analyzed
evidence package (CP-UNR-108F1 / firmware V1.00.14.01.R / CH1 / H.265).
Timestamp semantics are explicitly NOT resolved (see
`CPPlusRecordingRecord.timestamp_status`) and video is not decoded
(Phase 9 territory).
UNSUPPORTED: every other CP Plus model/firmware/export format.

See this evidence package's Phase 8 completion report for the full scope
statement.
"""

from __future__ import annotations

import io
from typing import IO

from app.acquisition.storage_reader import EvidenceStorageReader
from app.adapters.base import (
    AdapterCapability,
    AdapterResult,
    DVRAdapter,
    EvidenceBasis,
    SupportLevel,
)
from app.adapters.cp_plus.detector import DETECTION_HEADER_WINDOW, detect_cp_plus_structure
from app.adapters.cp_plus.extraction import CPVExtractionResult
from app.adapters.cp_plus.models import (
    KNOWN_CP_PLUS_SIGNATURES,
    CPPlusDetectionResult,
    CPPlusEnumerationResult,
    CPPlusParseStatus,
    CPPlusRecordingRecord,
    CPPlusSignature,
    to_recording_fields,
)
from app.adapters.cp_plus.parser import PARSER_VERSION, CPPlusParser
from app.adapters.cp_plus.recovery import (
    find_deleted_cpv_recordings,
    recover_damaged_cpv_segment,
)
from app.recovery import RecoveryStatus

__all__ = [
    "DETECTION_HEADER_WINDOW",
    "KNOWN_CP_PLUS_SIGNATURES",
    "PARSER_VERSION",
    "CPPlusAdapter",
    "CPPlusDetectionResult",
    "CPPlusEnumerationResult",
    "CPPlusParseStatus",
    "CPPlusParser",
    "CPPlusRecordingRecord",
    "CPPlusSignature",
    "CPVExtractionResult",
    "detect_cp_plus_structure",
    "to_recording_fields",
]


class CPPlusAdapter(DVRAdapter):
    """Vendor-level CP Plus adapter.

    Registers as a generic (`model_pattern=".*"`) CP Plus adapter because
    no specific model/firmware has been validated against real evidence
    (Master Specification Section 17: "Never report 'CP Plus fully
    supported' if only one model is tested.").

    Two usage modes, matching the `DVRAdapter` contract's split between
    declarative identity (must be determinable without evidence) and the
    Section 16 operation methods (which need evidence to operate on):

      - Constructed with no `reader` (`CPPlusAdapter()`): identity-only.
        This is what an `AdapterRegistry` should hold for pure
        vendor/model/firmware matching — it never touches any evidence.
      - Constructed with a `reader` bound to one evidence item's
        `EvidenceStorageReader`: the form a caller uses to actually run
        `inspect_storage`/`parse_filesystem`/`enumerate_recordings`/
        `normalize_evidence` against that evidence.
    """

    def __init__(
        self,
        reader: EvidenceStorageReader | None = None,
        *,
        source_evidence_id: str | None = None,
    ) -> None:
        self._reader = reader
        self._source_evidence_id = source_evidence_id
        self._parser = (
            CPPlusParser(reader, source_evidence_id=source_evidence_id)
            if reader is not None
            else None
        )

    @property
    def vendor(self) -> str:
        return "CP Plus"

    @property
    def model_pattern(self) -> str:
        return ".*"

    @property
    def capabilities(self) -> frozenset[AdapterCapability]:
        # Only capabilities genuinely, non-speculatively implemented against
        # the validated "ADIT-v1" signature — see module docstring.
        # TIMESTAMP_EXTRACTION is deliberately excluded: this adapter
        # preserves a raw counter but does not resolve it to a usable
        # timestamp (see CPPlusRecordingRecord.timestamp_status), so
        # claiming timestamp extraction would overstate what is validated.
        return frozenset(
            {
                AdapterCapability.FILESYSTEM_DETECTION,
                AdapterCapability.RECORDING_ENUMERATION,
                AdapterCapability.METADATA_EXTRACTION,
                AdapterCapability.RECORDING_EXTRACTION,
                # Damaged-recording recovery (`recover_recording`) is real,
                # validated recovery (Phase 10). Deleted-recording search
                # (`find_deleted_recordings`) is a real, tested, but
                # UNVALIDATED framework path — see
                # `app.adapters.cp_plus.recovery`'s module docstring. Both
                # share this one capability flag, matching how
                # `RECORDING_EXTRACTION` above already covers more than one
                # concrete method.
                AdapterCapability.RECOVERY,
            }
        )

    @property
    def adapter_version(self) -> str:
        return PARSER_VERSION

    @property
    def support_level(self) -> SupportLevel:
        # Phase 19: the only adapter in this codebase actually tested
        # against real, hash-verified project evidence -- see this
        # module's own CONTROLLED-EVIDENCE STATUS section above.
        return SupportLevel.LEVEL_4_VALIDATED

    @property
    def evidence_basis(self) -> tuple[EvidenceBasis, ...]:
        return (EvidenceBasis.REAL_PROJECT_EVIDENCE,)

    @property
    def model_scope(self) -> str:
        return (
            "validated only against CP-UNR-108F1 (hardware V1.0, firmware "
            "V1.00.14.01.R) with camera CP-UNC-TA21L3C-LQ (CH1, 1920x1080, H.265, "
            "continuous) -- see app.adapters.cp_plus.models module docstring"
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        return (
            "raw CPV timestamp counter is preserved but not resolved to a usable "
            "timestamp (see CPPlusRecordingRecord.timestamp_status)",
            "deleted-recording search (find_deleted_recordings) is a real, tested, "
            "but UNVALIDATED framework path -- no real deleted-record fixture exists",
            "only the 'ADIT-v1' container signature is recognized; any other CP "
            "Plus model/firmware/export tool reports UNSUPPORTED, never a guess",
        )

    def _require_parser(self) -> CPPlusParser:
        if self._parser is None:
            raise ValueError(
                "this CPPlusAdapter instance has no bound evidence reader; construct "
                "CPPlusAdapter(reader=...) to run storage/parsing operations (the "
                "no-reader form is for AdapterRegistry selection only)"
            )
        return self._parser

    def inspect_storage(self) -> AdapterResult:
        """Run CP Plus structure detection against the bound evidence reader."""
        detection = self._require_parser().validate_structure()
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format=detection.matched_signature,
            capability_set=self.capabilities,
            recordings=[],
            metadata={},
            recovery_candidates=[],
            warnings=[*detection.warnings, detection.reason],
            parser_version=self.adapter_version,
            confidence=1.0 if detection.status == CPPlusParseStatus.SUPPORTED_VALID else 0.0,
        )

    def parse_filesystem(self) -> AdapterResult:
        """Alias for `inspect_storage`: no distinct filesystem-parsing stage exists yet."""
        return self.inspect_storage()

    def enumerate_recordings(self) -> AdapterResult:
        """Run CP Plus recording enumeration against the bound evidence reader."""
        enumeration = self._require_parser().enumerate_recordings()
        confidence = (
            max(record.confidence for record in enumeration.recordings)
            if enumeration.recordings
            else 0.0
        )
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format="ADIT-v1" if enumeration.recordings else None,
            capability_set=self.capabilities,
            recordings=[record.recording_id for record in enumeration.recordings],
            metadata={},
            recovery_candidates=[],
            warnings=[*enumeration.warnings, enumeration.reason],
            parser_version=self.adapter_version,
            confidence=confidence,
        )

    def normalize_evidence(self) -> AdapterResult:
        """Produce this adapter's final normalized `AdapterResult`."""
        return self.enumerate_recordings()

    def extract_recording(
        self, recording_id: str, *, destination: IO[bytes] | None = None
    ) -> AdapterResult:
        """Reconstruct this evidence's HEVC elementary stream (Phase 9).

        Widens the `DVRAdapter.extract_recording` conceptual contract with
        an optional, keyword-only `destination`: this adapter is bound to
        exactly one CPV file (Section 16 — an adapter never owns
        cross-evidence orchestration), so a caller building a
        multi-segment session stream supplies the shared output handle to
        write into; `adapter.extract_recording(recording_id)` alone still
        works (writing to a discarded internal buffer) for a quick
        diagnostic-only call.

        Args:
            recording_id: Must match this evidence's single enumerated
                recording (see `enumerate_recordings`) — this adapter has
                nothing else to extract.
            destination: Where to append the extracted elementary-stream
                bytes. When `None`, an internal, discarded buffer is used
                — the returned `AdapterResult.metadata` still reports
                accurate counts either way.

        Returns:
            An `AdapterResult` whose `metadata` carries the extraction
            counts (as strings, per `AdapterResult`'s shape) and whose
            `warnings` carries anything `CPVExtractionResult.warnings`
            reported.
        """
        enumeration = self._require_parser().enumerate_recordings()
        known_ids = {record.recording_id for record in enumeration.recordings}
        if recording_id not in known_ids:
            return AdapterResult(
                vendor=self.vendor,
                model=None,
                firmware=None,
                detected_format=None,
                capability_set=self.capabilities,
                recordings=[],
                metadata={},
                recovery_candidates=[],
                warnings=[
                    f"recording_id {recording_id!r} does not match any recording enumerated "
                    f"from this evidence ({sorted(known_ids)!r})"
                ],
                parser_version=self.adapter_version,
                confidence=0.0,
            )

        sink = destination if destination is not None else io.BytesIO()
        result = self._require_parser().extract_elementary_stream(sink, segment_label=recording_id)
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format="ADIT-v1",
            capability_set=self.capabilities,
            recordings=[recording_id],
            metadata={
                "frames_written": str(result.frames_written),
                "keyframes_written": str(result.keyframes_written),
                "bytes_written": str(result.bytes_written),
                "skipped_video_fixed_auxiliary": str(result.skipped_video_fixed_auxiliary),
                "skipped_telemetry": str(result.skipped_telemetry),
                "skipped_unrecognized": str(result.skipped_unrecognized),
                "frames_missing_nal": str(result.frames_missing_nal),
                "truncated": str(result.truncated),
                "corrupted": str(result.corrupted),
            },
            recovery_candidates=[],
            warnings=list(result.warnings),
            parser_version=self.adapter_version,
            confidence=(
                0.0
                if result.frames_written == 0
                else (0.5 if (result.truncated or result.corrupted) else 1.0)
            ),
        )

    def find_deleted_recordings(self) -> AdapterResult:
        """Search for deleted-but-referenced recordings (Phase 10).

        RECOVERY FRAMEWORK / UNVALIDATED PATH: always reports
        `UNSUPPORTED` — see `app.adapters.cp_plus.recovery`'s module
        docstring for the evidence basis (no index/deletion-marker
        structure has ever been found in the ADIT-v1 container). This is
        real, deterministic, tested behavior, never a fabricated deleted-
        recording recovery.
        """
        result = find_deleted_cpv_recordings()
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format="ADIT-v1",
            capability_set=self.capabilities,
            recordings=[],
            metadata={"recovery_status": result.status.value},
            recovery_candidates=[],
            warnings=[result.reason],
            parser_version=self.adapter_version,
            confidence=0.0,
        )

    def recover_recording(
        self, recording_id: str, *, destination: IO[bytes] | None = None
    ) -> AdapterResult:
        """Recover the valid portion of one (possibly damaged) recording (Phase 10).

        REAL VALIDATED RECOVERY: reuses `extract_recording`'s exact byte
        reconstruction (`app.adapters.cp_plus.recovery.recover_damaged_cpv_segment`,
        itself built on Phase 9's `extract_hevc_elementary_stream`) and adds
        recovery-specific classification/confidence scoring on top.
        Demonstrated, in `tests/test_cp_plus_recovery_real_evidence_integration.py`,
        against the real evidence package's own genuinely truncated
        trailing record.

        Args:
            recording_id: Must match this evidence's single enumerated
                recording (see `enumerate_recordings`).
            destination: Where to append the recovered elementary-stream
                bytes. When `None`, an internal, discarded buffer is used.

        Returns:
            An `AdapterResult` whose `metadata["recovery_status"]` carries
            the authoritative `RecoveryStatus` this recovery attempt
            reached (never `"recovered"` for an incomplete/unverified
            result — see `recover_damaged_cpv_segment`).
        """
        enumeration = self._require_parser().enumerate_recordings()
        known_ids = {record.recording_id for record in enumeration.recordings}
        if recording_id not in known_ids:
            return AdapterResult(
                vendor=self.vendor,
                model=None,
                firmware=None,
                detected_format=None,
                capability_set=self.capabilities,
                recordings=[],
                metadata={"recovery_status": RecoveryStatus.FAILED.value},
                recovery_candidates=[],
                warnings=[
                    f"recording_id {recording_id!r} does not match any recording enumerated "
                    f"from this evidence ({sorted(known_ids)!r})"
                ],
                parser_version=self.adapter_version,
                confidence=0.0,
            )

        sink = destination if destination is not None else io.BytesIO()
        result = recover_damaged_cpv_segment(self._reader, sink, segment_label=recording_id)  # type: ignore[arg-type]
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format="ADIT-v1",
            capability_set=self.capabilities,
            recordings=[recording_id],
            metadata={
                "recovery_status": result.status.value,
                "bytes_recovered": str(result.bytes_recovered),
                "frames_recovered": str(result.frames_recovered),
                **(
                    {"frame_continuity": str(result.frame_continuity)}
                    if result.frame_continuity is not None
                    else {}
                ),
            },
            recovery_candidates=[],
            warnings=list(result.warnings),
            parser_version=self.adapter_version,
            confidence=result.confidence or 0.0,
        )

    def reconstruct_fragments(self, recording_id: str) -> AdapterResult:
        """Reconstruct fragment relationships for one recording (Phase 10).

        This adapter instance is bound to exactly one CPV segment (Section
        16 — an adapter never owns cross-evidence orchestration), so a
        *single* bound reader has nothing to reconstruct a relationship
        between. Real, evidence-validated multi-segment fragment
        reconstruction is available as the module-level
        `app.adapters.cp_plus.recovery.reconstruct_cpv_fragments`, used
        directly by `app.core.recovery_manager.RecoveryManager` once it has
        opened every candidate segment's reader in turn — exactly the same
        multi-evidence orchestration split Phase 9's
        `RecordingManager.link_session` already established.
        """
        return AdapterResult(
            vendor=self.vendor,
            model=None,
            firmware=None,
            detected_format="ADIT-v1",
            capability_set=self.capabilities,
            recordings=[recording_id],
            metadata={"recovery_status": RecoveryStatus.UNSUPPORTED.value},
            recovery_candidates=[],
            warnings=[
                "this adapter instance is bound to a single segment; multi-segment fragment "
                "reconstruction requires app.adapters.cp_plus.recovery.reconstruct_cpv_fragments "
                "called with every candidate segment's descriptor, orchestrated by "
                "app.core.recovery_manager.RecoveryManager"
            ],
            parser_version=self.adapter_version,
            confidence=0.0,
        )
