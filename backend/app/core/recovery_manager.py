"""
Business logic for the layered recovery engine (Phase 10, "Recovery Engine").

This is the DB-aware orchestration layer — mirrors
`app.core.recording_manager.RecordingManager` exactly: it opens/closes
`EvidenceStorageReader`s one at a time (never more than one at once), calls
into the CP Plus adapter/`app.recovery.*` modules for the actual layered
recovery logic, and persists the outcome as a `RecoveryResult` row plus a
recovered-bytes `Artifact` (reusing `EvidenceManager.register_artifact` and
the existing SHA-256/MD5 hashing — no new hashing/artifact code).

Vendor dispatch is CP Plus-only and explicit, for the same reason
`RecordingManager` already documents: no vendor is wired into
`AdapterRegistry` via real device identification yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.acquisition import open_reader
from app.adapters.base import AdapterCapability, AdapterResult
from app.adapters.cp_plus import PARSER_VERSION, CPPlusAdapter
from app.adapters.cp_plus.container import iter_cpv_records, parse_outer_header
from app.adapters.cp_plus.models import CPVRecordValidity
from app.adapters.cp_plus.recovery import (
    DELETED_RECOVERY_NOT_VALIDATED_STATEMENT,
    carve_cpv_records,
    find_deleted_cpv_recordings,
    reconstruct_cpv_fragments,
)
from app.adapters.cp_plus.session import segment_descriptor_from_header
from app.core.evidence_manager import EvidenceManager
from app.core.recording_manager import RecordingManager
from app.core.timestamp_manager import TimestampManager
from app.hashing.md5 import md5_file
from app.hashing.sha256 import sha256_file
from app.models import Case, Evidence, Recording, RecoveryResult
from app.recovery import RecoveryMethod, RecoveryStatus
from app.recovery.filesystem_recovery import FilesystemRecoveryOutcome
from app.recovery.recovery_engine import (
    RECOVERY_ENGINE_VERSION,
    RecoveryLayerCallables,
    RecoveryLayerResult,
    run_recovery_layers,
)
from app.schemas.artifact import ArtifactCreateRequest
from app.storage.artifact_store import prepare_artifact_directory

__all__ = ["RecoveryManager"]


class RecoveryManager:
    """Service layer for running and persisting layered recovery attempts."""

    @staticmethod
    def run_recovery(db: Session, recording_id: int) -> RecoveryResult:
        """Run the layered recovery engine against one `Recording` and persist the result.

        Never raises for a `PARTIAL`/`NO_RECOVERY_FOUND`/`UNSUPPORTED`/
        `FAILED` recovery *outcome* (Phase 10 task scope, section 11/"never
        silently fall through layers") — those are always reported via the
        returned `RecoveryResult.status`, never an exception. Only raises
        for programmer/caller-error-class problems.

        Args:
            db: Database session.
            recording_id: Primary key of the `Recording` to attempt
                recovery on (single-segment or session — both resolve the
                same way `RecordingManager.extract_recording` already does).

        Returns:
            The persisted `RecoveryResult`.

        Raises:
            ValueError: If the recording is not found, or a source segment
                evidence item cannot be resolved.
        """
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            raise ValueError(f"Recording with id {recording_id} not found")

        segments = RecordingManager._resolve_segments(db, recording)  # noqa: SLF001
        case = db.query(Case).filter(Case.id == recording.evidence.case_id).first()
        assert case is not None

        # Each call is a distinct, independently traceable recovery attempt
        # (Master Specification Section 51 rule 5's "append-oriented" spirit
        # — a later re-attempt must never silently overwrite/collide with an
        # earlier one's registered artifact), so every attempt gets its own
        # numbered subdirectory rather than a fixed per-recording path.
        attempt_number = (
            db.query(RecoveryResult).filter(RecoveryResult.recording_id == recording.id).count() + 1
        )
        relative_dir = (
            f"{case.case_id}/{recording.evidence.evidence_id}/recovery/candidates/"
            f"{recording.recording_id}/attempt-{attempt_number}"
        )
        recovered_path = prepare_artifact_directory(f"{relative_dir}/recovered.h265")

        callables = RecoveryLayerCallables(
            filesystem_recovery=RecoveryManager._filesystem_layer,
            vendor_recovery=lambda: RecoveryManager._vendor_recovery_layer(
                db, recording, segments, recovered_path
            ),
            carving=lambda: RecoveryManager._carving_layer(db, segments),
            fragment_reconstruction=lambda: RecoveryManager._fragment_reconstruction_layer(
                db, recording, segments
            ),
        )
        engine_result = run_recovery_layers(callables)
        final = engine_result.final

        artifact_id: int | None = None
        if final.status in (RecoveryStatus.RECOVERED, RecoveryStatus.PARTIAL) and (
            recovered_path.exists() and recovered_path.stat().st_size > 0
        ):
            artifact = EvidenceManager.register_artifact(
                db,
                recording.evidence_id,
                ArtifactCreateRequest(
                    relative_path=f"{relative_dir}/recovered.h265",
                    artifact_type="cp_plus_recovered_hevc_elementary_stream",
                    size_bytes=recovered_path.stat().st_size,
                    sha256=sha256_file(recovered_path),
                    md5=md5_file(recovered_path),
                    tool_version=PARSER_VERSION,
                ),
            )
            artifact_id = artifact.id
            recording.recovery_status = final.status.value
            recording.recovery_method = final.method.value
            recording.confidence = final.confidence

        result = RecoveryResult(
            evidence_id=recording.evidence_id,
            recording_id=recording.id,
            artifact_id=artifact_id,
            method=final.method.value,
            status=final.status.value,
            fragments_found=final.fragments_found,
            fragments_used=final.fragments_used,
            fragments_missing=final.fragments_missing,
            frames_expected=None,
            frames_recovered=final.frames_recovered,
            recovery_rate=None,
            # Phase 11: reuses whatever normalization already exists for
            # this recording (never computed here) — `None` unless a
            # VERIFIED clock-offset normalization was already run via
            # `TimestampManager.normalize_recording`.
            timestamp_error=TimestampManager.resolve_timestamp_error(db, recording),
            frame_continuity=final.frame_continuity,
            confidence=final.confidence,
            # `source_offset`/`source_length` describe a single byte range
            # in the *source* evidence — left unset for a multi-segment
            # recording (no single such range applies) rather than
            # misrepresenting the recovered-output size as a source range.
            source_offset=None,
            source_length=None,
            recovery_engine_version=RECOVERY_ENGINE_VERSION,
            parser_version=PARSER_VERSION,
            notes=RecoveryManager._build_notes(engine_result.layers, final),
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result

    @staticmethod
    def list_recovery_results(db: Session, evidence_id: int) -> list[RecoveryResult]:
        """List every recovery attempt recorded against one evidence item.

        Args:
            db: Database session.
            evidence_id: Primary key of the evidence to query.

        Returns:
            `RecoveryResult` rows, newest first.
        """
        return (
            db.query(RecoveryResult)
            .filter(RecoveryResult.evidence_id == evidence_id)
            .order_by(RecoveryResult.created_at.desc())
            .all()
        )

    # --- layer implementations ---------------------------------------------

    @staticmethod
    def _filesystem_layer() -> FilesystemRecoveryOutcome:
        """Layer 1: CP Plus has no discoverable index/seek-table (Phase 8 finding)."""
        result = find_deleted_cpv_recordings()
        return FilesystemRecoveryOutcome(
            status=result.status, reason=result.reason, recovered_recording_ids=[]
        )

    @staticmethod
    def _vendor_recovery_layer(
        db: Session, recording: Recording, segments: list[dict[str, Any]], output_path: Path
    ) -> AdapterResult:
        """Layer 2: damaged-recording recovery, across every source segment in order.

        Opens one segment reader at a time (never more than one at once,
        matching `RecordingManager.extract_recording`'s established
        pattern) and appends each segment's recovered bytes to one shared
        output file.
        """
        warnings: list[str] = []
        total_bytes = 0
        total_frames = 0
        continuity_values: list[float] = []
        confidences: list[float] = []
        statuses: list[RecoveryStatus] = []

        with output_path.open("wb") as output:
            for segment in segments:
                evidence = db.query(Evidence).filter(Evidence.id == segment["evidence_pk"]).first()
                if not evidence or not evidence.source_path:
                    raise ValueError(
                        f"source segment evidence {segment['evidence_pk']} could not be "
                        "resolved for recovery"
                    )
                reader = open_reader(evidence.source_type, Path(evidence.source_path))
                try:
                    adapter = CPPlusAdapter(reader, source_evidence_id=evidence.evidence_id)
                    result = adapter.recover_recording(
                        segment["segment_recording_id"], destination=output
                    )
                finally:
                    reader.close()

                warnings.extend(result.warnings)
                total_bytes += int(result.metadata.get("bytes_recovered") or "0")
                total_frames += int(result.metadata.get("frames_recovered") or "0")
                continuity_raw = result.metadata.get("frame_continuity")
                if continuity_raw is not None:
                    continuity_values.append(float(continuity_raw))
                if result.confidence:
                    confidences.append(result.confidence)
                raw_status = result.metadata.get("recovery_status")
                if raw_status:
                    statuses.append(RecoveryStatus(raw_status))

        if not statuses or total_bytes == 0:
            overall_status = RecoveryStatus.NO_RECOVERY_FOUND
        elif all(status == RecoveryStatus.RECOVERED for status in statuses):
            overall_status = RecoveryStatus.RECOVERED
        else:
            overall_status = RecoveryStatus.PARTIAL

        metadata = {
            "recovery_status": overall_status.value,
            "bytes_recovered": str(total_bytes),
            "frames_recovered": str(total_frames),
        }
        if continuity_values:
            metadata["frame_continuity"] = str(sum(continuity_values) / len(continuity_values))

        return AdapterResult(
            vendor="CP Plus",
            model=None,
            firmware=None,
            detected_format="ADIT-v1",
            capability_set=frozenset({AdapterCapability.RECOVERY}),
            recordings=[recording.recording_id],
            metadata=metadata,
            recovery_candidates=[],
            warnings=warnings,
            parser_version=PARSER_VERSION,
            confidence=(sum(confidences) / len(confidences)) if confidences else 0.0,
        )

    @staticmethod
    def _carving_layer(db: Session, segments: list[dict[str, Any]]) -> RecoveryLayerResult:
        """Layer 3: signature-scan every source segment for `CPAV` record magics
        the normal sequential walk did not already reach.

        Honest by construction (Master Specification Section 23: "never
        present a carved candidate as an unquestionable original
        recording"): reports how many *additional* valid record boundaries
        carving found past each segment's sequential-walk stop point, but
        does not itself splice them into a recovered stream — that would
        require re-running extraction from an unverified mid-file offset,
        which is exactly the kind of unverified-candidate promotion Section
        23 warns against.
        """
        extra_candidates = 0
        warnings: list[str] = []
        for segment in segments:
            evidence = db.query(Evidence).filter(Evidence.id == segment["evidence_pk"]).first()
            if not evidence or not evidence.source_path:
                continue
            reader = open_reader(evidence.source_type, Path(evidence.source_path))
            try:
                known_valid_offsets: set[int] = set()
                for record in iter_cpv_records(reader):
                    if record.validity != CPVRecordValidity.VALID:
                        break
                    known_valid_offsets.add(record.offset)
                carve_result = carve_cpv_records(
                    reader, known_valid_offsets=frozenset(known_valid_offsets)
                )
            finally:
                reader.close()

            new_valid = [
                r for r in carve_result.records if r.valid and not r.also_found_by_sequential_walk
            ]
            if new_valid:
                extra_candidates += len(new_valid)
                warnings.append(
                    f"{segment['segment_recording_id']}: carving found {len(new_valid)} valid "
                    "CPAV record(s) at offset(s) past the sequential-walk stop point — "
                    f"{[c.offset for c in new_valid]}; reported as a candidate only, not "
                    "spliced into any recovered output"
                )

        if extra_candidates == 0:
            return RecoveryLayerResult(
                method=RecoveryMethod.CARVING,
                status=RecoveryStatus.NO_RECOVERY_FOUND,
                reason=(
                    "signature scanning found no valid CPAV record boundaries beyond what "
                    "sequential walking already reached"
                ),
            )
        return RecoveryLayerResult(
            method=RecoveryMethod.CARVING,
            status=RecoveryStatus.PARTIAL,
            reason=f"carving found {extra_candidates} additional valid record candidate(s)",
            fragments_found=extra_candidates,
            warnings=warnings,
        )

    @staticmethod
    def _fragment_reconstruction_layer(
        db: Session, recording: Recording, segments: list[dict[str, Any]]
    ) -> AdapterResult:
        """Layer 4: independently re-verify segment order/continuity by counter,
        never trusting whatever order the segments were already linked in
        (Phase 9's `RecordingManager.link_session`, or filename order for a
        single-segment recording)."""
        descriptors = []
        for segment in segments:
            evidence = db.query(Evidence).filter(Evidence.id == segment["evidence_pk"]).first()
            if not evidence or not evidence.source_path:
                raise ValueError(
                    f"source segment evidence {segment['evidence_pk']} could not be resolved "
                    "for fragment reconstruction"
                )
            reader = open_reader(evidence.source_type, Path(evidence.source_path))
            try:
                header = parse_outer_header(reader)
            finally:
                reader.close()
            descriptors.append(segment_descriptor_from_header(evidence.evidence_id, header))

        link_result = reconstruct_cpv_fragments(descriptors)

        fragments_missing = sum(
            1 for link in link_result.links if link.status.value == "missing_segment"
        )
        if link_result.overall_status.value == "continuous":
            status = RecoveryStatus.RECOVERED
        elif link_result.overall_status.value == "unknown":
            status = RecoveryStatus.UNSUPPORTED
        else:
            status = RecoveryStatus.PARTIAL

        return AdapterResult(
            vendor="CP Plus",
            model=None,
            firmware=None,
            detected_format="ADIT-v1",
            capability_set=frozenset({AdapterCapability.RECOVERY}),
            recordings=[recording.recording_id],
            metadata={
                "recovery_status": status.value,
                "fragments_found": str(len(descriptors)),
                "fragments_used": str(len(descriptors) - fragments_missing),
                "fragments_missing": str(fragments_missing),
            },
            recovery_candidates=[],
            warnings=list(link_result.warnings),
            parser_version=PARSER_VERSION,
            confidence=1.0 if link_result.overall_status.value == "continuous" else 0.5,
        )

    @staticmethod
    def _build_notes(layers: list[RecoveryLayerResult], final: RecoveryLayerResult) -> str:
        lines = [f"final: {final.method.value} -> {final.status.value}: {final.reason}"]
        for layer in layers:
            lines.append(f"{layer.method.value}: {layer.status.value} - {layer.reason}")
        if (
            final.status == RecoveryStatus.UNSUPPORTED
            and final.method == RecoveryMethod.FILESYSTEM_INDEX
        ):
            lines.append(DELETED_RECOVERY_NOT_VALIDATED_STATEMENT)
        return "\n".join(lines)
