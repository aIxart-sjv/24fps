"""
Business logic for recording enumeration, multi-segment session linking,
and extraction (Phase 9, "Recording Extraction + FFmpeg").

This is the orchestration layer Master Specification Section 16 assigns to
"the common engine" (evidence objects, provenance) rather than to a vendor
adapter: it opens/closes `EvidenceStorageReader`s one at a time (never more
than one at once, matching `app.adapters.cp_plus.session`'s own documented
contract), calls into the CP Plus adapter/parser for vendor-specific
structure understanding, calls into `app.media` for FFmpeg, and persists
the result as `Recording`/`RecordingMetadata`/`Artifact` rows.

Vendor dispatch is currently CP Plus-only and explicit (this evidence
either matches the validated "ADIT-v1" structure or it does not) rather
than routed through `app.adapters.registry.AdapterRegistry` +
`app.models.device.Device` identification: nothing in `app.detection`
currently populates a device's vendor as `"CP Plus"`, so registry-based
dispatch would not actually select this adapter today. Wiring that up is a
Phase 6/7 gap, not this phase's job — see the Phase 9 plan for the full
rationale. A second real vendor adapter should prompt revisiting this.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.acquisition import open_reader
from app.adapters.cp_plus import PARSER_VERSION, CPPlusAdapter, CPPlusParser
from app.adapters.cp_plus.container import parse_outer_header
from app.adapters.cp_plus.models import (
    CPPlusParseStatus,
    CPVSegmentDescriptor,
    to_recording_fields,
)
from app.adapters.cp_plus.session import (
    link_cpv_session,
    segment_descriptor_from_header,
)
from app.core.evidence_manager import EvidenceManager
from app.hashing.md5 import md5_file
from app.hashing.sha256 import sha256_file
from app.media.decoder import mux_hevc_annexb_to_mp4, transcode_to_h264_mp4
from app.media.ffmpeg import get_ffmpeg_version
from app.media.media_probe import probe_media
from app.models import Case, Evidence, Recording, RecordingMetadata
from app.schemas.artifact import ArtifactCreateRequest
from app.storage.artifact_store import prepare_artifact_directory

_UNSUPPORTED_STATUSES = frozenset({CPPlusParseStatus.UNKNOWN, CPPlusParseStatus.UNSUPPORTED})

#: `RecordingMetadata.key` for the ordered, JSON-encoded list of
#: `{"evidence_pk", "evidence_business_id", "segment_recording_id",
#: "filename"}` a session `Recording` was linked from.
_SOURCE_SEGMENTS_KEY = "source_segments"


class RecordingManager:
    """Service layer for CP Plus recording discovery, linking, and extraction."""

    # --- enumeration -----------------------------------------------------

    @staticmethod
    def enumerate_recordings(db: Session, evidence_id: int) -> list[Recording]:
        """Discover recordings on one evidence item and persist them.

        Idempotent: safe to call more than once against the same evidence
        (updates the existing `Recording` row rather than duplicating it),
        matching `EvidenceManager.identify_device`'s established pattern.

        Args:
            db: Database session.
            evidence_id: Primary key of the evidence to inspect.

        Returns:
            The `Recording` rows discovered — empty (not an error) when
            this evidence does not match a supported CP Plus structure.

        Raises:
            ValueError: If evidence is not found or has no `source_path`.
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence with id {evidence_id} not found")
        if not evidence.source_path:
            raise ValueError(f"Evidence with id {evidence_id} has no source_path to inspect")

        recording, _descriptor = RecordingManager._ensure_segment_recording(db, evidence)
        return [recording] if recording is not None else []

    @staticmethod
    def _ensure_segment_recording(
        db: Session, evidence: Evidence
    ) -> tuple[Recording | None, CPVSegmentDescriptor | None]:
        """Open `evidence`'s reader once and both enumerate and header-parse it.

        Internal helper shared by `enumerate_recordings` (which only needs
        the `Recording`) and `link_session` (which also needs a
        `CPVSegmentDescriptor` for counter-based linking) so a segment's
        reader is only ever opened once per call, never twice.

        Returns:
            `(recording, descriptor)`, both `None` when this evidence does
            not match a supported CP Plus structure.
        """
        assert evidence.source_path is not None  # enforced by callers
        reader = open_reader(evidence.source_type, Path(evidence.source_path))
        try:
            parser = CPPlusParser(reader, source_evidence_id=evidence.evidence_id)
            enumeration = parser.enumerate_recordings()
            if enumeration.status in _UNSUPPORTED_STATUSES or not enumeration.recordings:
                return None, None

            cp_record = enumeration.recordings[0]
            fields = to_recording_fields(cp_record)

            recording = (
                db.query(Recording)
                .filter(Recording.recording_id == cp_record.recording_id)
                .first()
            )
            if recording is None:
                recording = Recording(evidence_id=evidence.id, **fields)
                db.add(recording)
            else:
                for key, value in fields.items():
                    setattr(recording, key, value)
            db.commit()
            db.refresh(recording)

            RecordingManager._set_metadata(db, recording, "vendor", "CP Plus")
            RecordingManager._set_metadata(db, recording, "parser_version", cp_record.parser_version)
            RecordingManager._set_metadata(
                db, recording, "timestamp_status", cp_record.timestamp_status.value
            )
            if cp_record.timestamp_source is not None:
                RecordingManager._set_metadata(
                    db, recording, "timestamp_source", cp_record.timestamp_source
                )
            if cp_record.raw_timestamp is not None:
                RecordingManager._set_metadata(
                    db, recording, "raw_timestamp", str(cp_record.raw_timestamp)
                )

            header = parse_outer_header(reader)
            descriptor = segment_descriptor_from_header(evidence.evidence_id, header)
            return recording, descriptor
        finally:
            reader.close()

    # --- session linking ---------------------------------------------------

    @staticmethod
    def link_session(db: Session, evidence_ids: list[int]) -> Recording:
        """Link an ordered sequence of CP Plus segments into one session `Recording`.

        Args:
            db: Database session.
            evidence_ids: Primary keys of the segment evidence items, in
                caller-asserted playback order (the caller's provenance —
                e.g. the export filenames' own start timestamps; this
                method never reorders them, matching
                `app.adapters.cp_plus.session.link_cpv_session`'s own
                contract).

        Returns:
            The session-level `Recording` (idempotent: re-linking the same
            ordered evidence set updates the existing session row rather
            than duplicating it).

        Raises:
            ValueError: If fewer than 2 evidence ids are given, any
                evidence is not found / has no `source_path` / does not
                belong to the same case as the others, or any segment does
                not match a supported CP Plus structure.
        """
        if len(evidence_ids) < 2:
            raise ValueError("link_session requires at least 2 evidence ids")

        segments: list[Recording] = []
        descriptors: list[CPVSegmentDescriptor] = []
        case_id: int | None = None
        for evidence_id in evidence_ids:
            evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
            if not evidence:
                raise ValueError(f"Evidence with id {evidence_id} not found")
            if not evidence.source_path:
                raise ValueError(f"Evidence with id {evidence_id} has no source_path to inspect")
            if case_id is None:
                case_id = evidence.case_id
            elif evidence.case_id != case_id:
                raise ValueError(
                    f"Evidence with id {evidence_id} belongs to a different case than the "
                    "other segments; a session can only link segments from one case"
                )

            recording, descriptor = RecordingManager._ensure_segment_recording(db, evidence)
            if recording is None or descriptor is None:
                raise ValueError(
                    f"Evidence with id {evidence_id} does not match a supported CP Plus "
                    "structure; cannot include it in a session link"
                )
            segments.append(recording)
            descriptors.append(descriptor)

        link_result = link_cpv_session(descriptors)

        case = db.query(Case).filter(Case.id == case_id).first()
        assert case is not None  # already validated via the evidence FK above
        anchor_evidence_id = evidence_ids[0]
        session_recording_id = f"SESSION-{case.case_id}-{segments[0].recording_id}"

        first, last = segments[0], segments[-1]
        duration_ms: int | None = None
        if first.start_original is not None and last.end_original is not None:
            duration_ms = int((last.end_original - first.start_original).total_seconds() * 1000)

        confidences = [s.confidence for s in segments if s.confidence is not None]

        session_recording = (
            db.query(Recording).filter(Recording.recording_id == session_recording_id).first()
        )
        if session_recording is None:
            session_recording = Recording(
                evidence_id=anchor_evidence_id, recording_id=session_recording_id
            )
            db.add(session_recording)

        session_recording.camera_id = first.camera_id
        session_recording.channel = first.channel
        session_recording.start_original = first.start_original
        session_recording.end_original = last.end_original
        session_recording.duration_ms = duration_ms
        session_recording.source_location = f"cpv_session:{len(segments)} segments"
        session_recording.confidence = min(confidences) if confidences else None
        db.commit()
        db.refresh(session_recording)

        segment_payload = [
            {
                "evidence_pk": evidence_id,
                "evidence_business_id": segment.evidence.evidence_id,
                "segment_recording_id": segment.recording_id,
            }
            for evidence_id, segment in zip(evidence_ids, segments, strict=True)
        ]
        RecordingManager._set_metadata(
            db, session_recording, _SOURCE_SEGMENTS_KEY, json.dumps(segment_payload)
        )
        RecordingManager._set_metadata(db, session_recording, "vendor", "CP Plus")
        RecordingManager._set_metadata(db, session_recording, "parser_version", PARSER_VERSION)
        RecordingManager._set_metadata(
            db, session_recording, "segment_count", str(len(segments))
        )
        RecordingManager._set_metadata(
            db, session_recording, "session_link_status", link_result.overall_status.value
        )
        if link_result.warnings:
            RecordingManager._set_metadata(
                db, session_recording, "session_link_warnings", json.dumps(link_result.warnings)
            )

        return session_recording

    # --- extraction --------------------------------------------------------

    @staticmethod
    def extract_recording(db: Session, recording_id: int) -> Recording:
        """Reconstruct, mux, and register the playable output for one recording.

        Never raises for a partial/failed *extraction* outcome (Master
        Specification Section 11/54 partial-parsing rules) — the result is
        always reported via the `extraction_status`/`extraction_warnings`
        metadata entries on the returned `Recording`. Only raises for
        programmer/caller-error-class problems.

        Args:
            db: Database session.
            recording_id: Primary key of the `Recording` to extract.

        Returns:
            The updated `Recording`.

        Raises:
            ValueError: If the recording is not found, or a source segment
                evidence item cannot be resolved.
        """
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            raise ValueError(f"Recording with id {recording_id} not found")

        segments = RecordingManager._resolve_segments(db, recording)

        case = db.query(Case).filter(Case.id == recording.evidence.case_id).first()
        assert case is not None
        relative_dir = f"{case.case_id}/{recording.evidence.evidence_id}/recordings/{recording.recording_id}"
        elementary_stream_path = prepare_artifact_directory(f"{relative_dir}/elementary_stream.h265")

        warnings: list[str] = []
        total_bytes = 0
        any_truncated = False
        any_corrupted = False
        with elementary_stream_path.open("wb") as output:
            for segment in segments:
                evidence = db.query(Evidence).filter(Evidence.id == segment["evidence_pk"]).first()
                if not evidence or not evidence.source_path:
                    raise ValueError(
                        f"source segment evidence {segment['evidence_pk']} could not be "
                        "resolved for extraction"
                    )
                reader = open_reader(evidence.source_type, Path(evidence.source_path))
                try:
                    adapter = CPPlusAdapter(reader, source_evidence_id=evidence.evidence_id)
                    result = adapter.extract_recording(
                        segment["segment_recording_id"], destination=output
                    )
                finally:
                    reader.close()
                total_bytes += int(result.metadata.get("bytes_written", "0"))
                warnings.extend(result.warnings)
                # `warnings` also carries benign, expected notices (e.g. the
                # trailing 0xFF end-of-real-records padding every real
                # segment ends with) that must not, on their own, downgrade
                # extraction_status — only genuine truncation/corruption
                # does (see app.adapters.cp_plus.models.CPVRecordValidity's
                # own TRAILING_PADDING-vs-corruption distinction).
                any_truncated = any_truncated or result.metadata.get("truncated") == "True"
                any_corrupted = any_corrupted or result.metadata.get("corrupted") == "True"

        if total_bytes == 0:
            RecordingManager._set_metadata(db, recording, "extraction_status", "failed")
            RecordingManager._set_metadata(
                db, recording, "extraction_warnings", json.dumps(warnings)
            )
            db.commit()
            db.refresh(recording)
            return recording

        stream_artifact = EvidenceManager.register_artifact(
            db,
            recording.evidence_id,
            ArtifactCreateRequest(
                relative_path=f"{relative_dir}/elementary_stream.h265",
                artifact_type="cp_plus_hevc_elementary_stream",
                size_bytes=elementary_stream_path.stat().st_size,
                sha256=sha256_file(elementary_stream_path),
                md5=md5_file(elementary_stream_path),
                tool_version=get_ffmpeg_version(),
            ),
        )

        extraction_status = "partial" if (any_truncated or any_corrupted) else "successful"

        master_path = prepare_artifact_directory(f"{relative_dir}/master_h265.mp4")
        mux_result = mux_hevc_annexb_to_mp4(elementary_stream_path, master_path)
        if mux_result.ok:
            probe = probe_media(master_path)
            if probe.available:
                recording.codec = probe.codec
                recording.container = "mp4"
                recording.width = probe.width
                recording.height = probe.height
                recording.fps = probe.fps
                if probe.duration_seconds is not None:
                    recording.duration_ms = int(probe.duration_seconds * 1000)
                warnings.extend(probe.warnings)

            master_artifact = EvidenceManager.register_artifact(
                db,
                recording.evidence_id,
                ArtifactCreateRequest(
                    relative_path=f"{relative_dir}/master_h265.mp4",
                    artifact_type="cp_plus_hevc_master_mp4",
                    parent_artifact_id=stream_artifact.id,
                    size_bytes=master_path.stat().st_size,
                    sha256=sha256_file(master_path),
                    md5=md5_file(master_path),
                    tool_version=get_ffmpeg_version(),
                ),
            )
            recording.artifact_id = str(master_artifact.id)
        else:
            extraction_status = "partial"
            warnings.append(f"ffmpeg mux to H.265 master MP4 failed: {mux_result.stderr[-2000:]}")

        preview_path = prepare_artifact_directory(f"{relative_dir}/preview_h264.mp4")
        transcode_result = transcode_to_h264_mp4(elementary_stream_path, preview_path)
        if transcode_result.ok:
            preview_artifact = EvidenceManager.register_artifact(
                db,
                recording.evidence_id,
                ArtifactCreateRequest(
                    relative_path=f"{relative_dir}/preview_h264.mp4",
                    artifact_type="cp_plus_h264_preview_mp4",
                    parent_artifact_id=stream_artifact.id,
                    size_bytes=preview_path.stat().st_size,
                    sha256=sha256_file(preview_path),
                    md5=md5_file(preview_path),
                    tool_version=get_ffmpeg_version(),
                ),
            )
            RecordingManager._set_metadata(
                db, recording, "preview_artifact_id", str(preview_artifact.id)
            )
        else:
            warnings.append(
                f"ffmpeg transcode to H.264 preview MP4 failed: {transcode_result.stderr[-2000:]}"
            )

        db.commit()
        db.refresh(recording)

        RecordingManager._set_metadata(db, recording, "extraction_status", extraction_status)
        RecordingManager._set_metadata(db, recording, "extraction_warnings", json.dumps(warnings))
        RecordingManager._set_metadata(
            db, recording, "elementary_stream_artifact_id", str(stream_artifact.id)
        )
        ffmpeg_version = get_ffmpeg_version()
        if ffmpeg_version is not None:
            RecordingManager._set_metadata(db, recording, "ffmpeg_version", ffmpeg_version)

        db.commit()
        db.refresh(recording)
        return recording

    @staticmethod
    def _resolve_segments(db: Session, recording: Recording) -> list[dict[str, Any]]:
        """Return the ordered list of source segments a `Recording` was built from.

        A session `Recording` (produced by `link_session`) carries this as
        a `source_segments` metadata entry; a single-segment `Recording`
        (produced by `enumerate_recordings` alone) has no such entry and is
        treated as its own one-element segment list.
        """
        entry = (
            db.query(RecordingMetadata)
            .filter(
                RecordingMetadata.recording_id == recording.id,
                RecordingMetadata.key == _SOURCE_SEGMENTS_KEY,
            )
            .first()
        )
        if entry is None or entry.value is None:
            return [
                {
                    "evidence_pk": recording.evidence_id,
                    "segment_recording_id": recording.recording_id,
                }
            ]
        payload: list[dict[str, Any]] = json.loads(entry.value)
        return payload

    @staticmethod
    def _set_metadata(
        db: Session,
        recording: Recording,
        key: str,
        value: str,
        *,
        source: str | None = None,
        confidence: float | None = None,
    ) -> RecordingMetadata:
        """Upsert one `RecordingMetadata` entry for `recording` (idempotent by key)."""
        entry = (
            db.query(RecordingMetadata)
            .filter(RecordingMetadata.recording_id == recording.id, RecordingMetadata.key == key)
            .first()
        )
        if entry is None:
            entry = RecordingMetadata(recording_id=recording.id, key=key)
            db.add(entry)
        entry.value = value
        entry.source = source
        entry.confidence = confidence
        db.commit()
        db.refresh(entry)
        return entry
