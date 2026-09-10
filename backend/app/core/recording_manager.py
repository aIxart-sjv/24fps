"""
Business logic for recording enumeration, multi-segment session linking,
and extraction (Phase 9, "Recording Extraction + FFmpeg").

This is the orchestration layer Master Specification Section 16 assigns to
"the common engine" (evidence objects, provenance) rather than to a vendor
adapter: it opens/closes `EvidenceStorageReader`s one at a time (never more
than one at once, matching `app.adapters.cp_plus.session`'s own documented
contract), calls into the vendor-specific adapter/parser for
vendor-specific structure understanding, calls into `app.media` for
FFmpeg, and persists the result as `Recording`/`RecordingMetadata`/
`Artifact` rows.

Vendor dispatch is explicit and try-in-order (`_ensure_segment_recording`
tries CP Plus's binary "ADIT-v1" structure match first, then Hikvision's
export-filename+sidecar-log identification, Phase 26) rather than routed
through `app.adapters.registry.AdapterRegistry`: nothing in
`app.detection` can determine vendor from generic container inspection
alone, so registry-based dispatch cannot yet select the right adapter
*before* this module has already tried each one. Once this module
confirms a match, though, it does write that confirmation back onto
`Device` (via `EvidenceManager.confirm_vendor`, Phase 24) so downstream
consumers (acquisition/identification API responses) see the real vendor
rather than `app.detection.device_identifier`'s generic, deliberately
vendor-blind result. Extraction (`extract_recording`) branches on the
persisted `vendor` `RecordingMetadata` entry: CP Plus's own proprietary-
container reconstruction pipeline is unchanged; Hikvision's exported clip
already being a standard container, its own `_extract_hikvision_recording`
skips reconstruction entirely and remuxes/transcodes directly from the
preserved source evidence file. A third real vendor adapter should prompt
revisiting the dispatch side of this gap into something more structured.
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
from app.adapters.hikvision.models import HikvisionClipIdentificationStatus
from app.adapters.hikvision.models import to_recording_fields as hikvision_to_recording_fields
from app.adapters.hikvision.parser import HikvisionParser
from app.core.evidence_manager import EvidenceManager
from app.hashing.md5 import md5_file
from app.hashing.sha256 import sha256_file
from app.media.decoder import (
    mux_hevc_annexb_to_mp4,
    remux_container_to_mp4,
    transcode_container_to_h264_aac_mp4,
    transcode_to_h264_mp4,
)
from app.media.ffmpeg import get_ffmpeg_version
from app.media.media_probe import probe_media
from app.models import Artifact, Case, Evidence, Recording, RecordingMetadata
from app.schemas.artifact import ArtifactCreateRequest
from app.storage.artifact_store import prepare_artifact_directory

_UNSUPPORTED_STATUSES = frozenset({CPPlusParseStatus.UNKNOWN, CPPlusParseStatus.UNSUPPORTED})

#: Vendor-identification confidence once this evidence's container has
#: been successfully parsed against CP Plus's own documented "ADIT-v1"
#: recording structure (task Phase 24 scope, "Acquisition Metadata -- Fix
#: Accuracy"). This is confidence that the structure genuinely *is* CP
#: Plus's format -- as strong a basis as `app.detection.device_identifier`
#: gives a verified container signature -- not a statement about whether
#: this particular recording's data is intact (`Recording.confidence`, a
#: separate field, already carries that; a `SUPPORTED_CORRUPTED`/
#: `SUPPORTED_PARTIAL` status still definitively identifies the vendor).
_CP_PLUS_VENDOR_CONFIDENCE = 1.0
_CP_PLUS_IDENTIFICATION_METHOD = "cp_plus_structure_signature"

#: Phase 26: identification method recorded on `Device.identification_method`
#: once a Hikvision export filename + same-stem export-log sidecar have
#: been positively cross-checked (`HikvisionClipIdentificationStatus.
#: CONFIRMED_BY_EXPORT_LOG`) -- see `app.adapters.hikvision.parser`'s
#: module docstring for why this, not an in-container signature, is this
#: vendor's own strongest available identification evidence.
_HIKVISION_IDENTIFICATION_METHOD = "hikvision_export_log_sidecar"

#: `RecordingMetadata.key` for the ordered, JSON-encoded list of
#: `{"evidence_pk", "evidence_business_id", "segment_recording_id",
#: "filename"}` a session `Recording` was linked from.
_SOURCE_SEGMENTS_KEY = "source_segments"

#: `Recording` columns whose only authoritative source is an actual
#: `ffprobe` pass over produced derived media (`extract_recording`'s own
#: mux+probe step, or `refresh_media_metadata`'s re-probe), plus the
#: `artifact_id` FK that pass establishes -- CP Plus's own container
#: format never carries any of them (`to_recording_fields`' docstring), so
#: `to_recording_fields` always maps them to `None`.
#: `_ensure_segment_recording`'s enumeration-update path must never
#: overwrite an existing `Recording` row's real values with those `None`
#: placeholders.
_MEDIA_PROBE_OWNED_FIELDS = frozenset(
    {"codec", "container", "width", "height", "fps", "duration_ms", "artifact_id"}
)


class RecordingManager:
    """Service layer for recording discovery, linking, and extraction
    (CP Plus and, since Phase 26, Hikvision)."""

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
            this evidence does not match any supported vendor structure
            (CP Plus's binary "ADIT-v1" signature, or Hikvision's export
            filename + sidecar-log identification).

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
        """Open `evidence`'s reader once and try each supported vendor in turn.

        Internal helper shared by `enumerate_recordings` (which only needs
        the `Recording`) and `link_session` (which also needs a
        `CPVSegmentDescriptor` for counter-based linking, a CP Plus-only
        concept -- `None` for every other vendor) so a segment's reader is
        only ever opened once per call, never twice.

        Tries CP Plus's binary structure match first (unchanged from
        Phase 9), then Hikvision's sidecar-log-based exported-clip
        identification (Phase 26) -- CP Plus's own detector safely reports
        `UNSUPPORTED`/`UNKNOWN` for non-matching bytes (never raises), so
        trying it against Hikvision evidence first costs nothing and keeps
        CP Plus's own dispatch precedence exactly as documented in this
        module's own docstring.

        Returns:
            `(recording, descriptor)`. `descriptor` is `None` for every
            vendor except CP Plus (session linking is a CP Plus-only
            concept -- see `link_session`). Both are `None` when this
            evidence matches no supported vendor structure.
        """
        assert evidence.source_path is not None  # enforced by callers
        reader = open_reader(evidence.source_type, Path(evidence.source_path))
        try:
            recording, descriptor = RecordingManager._try_cp_plus_segment(db, evidence, reader)
            if recording is not None:
                return recording, descriptor

            recording = RecordingManager._try_hikvision_recording(db, evidence, reader)
            return recording, None
        finally:
            reader.close()

    @staticmethod
    def _try_cp_plus_segment(
        db: Session, evidence: Evidence, reader: Any
    ) -> tuple[Recording | None, CPVSegmentDescriptor | None]:
        """Try CP Plus's binary "ADIT-v1" structure match against `reader`.

        Returns:
            `(recording, descriptor)`, both `None` when this evidence does
            not match a supported CP Plus structure.
        """
        parser = CPPlusParser(reader, source_evidence_id=evidence.evidence_id)
        enumeration = parser.enumerate_recordings()
        if enumeration.status in _UNSUPPORTED_STATUSES or not enumeration.recordings:
            return None, None

        cp_record = enumeration.recordings[0]
        fields = to_recording_fields(cp_record)

        recording = (
            db.query(Recording).filter(Recording.recording_id == cp_record.recording_id).first()
        )
        if recording is None:
            recording = Recording(evidence_id=evidence.id, **fields)
            db.add(recording)
        else:
            # `fields` always carries `to_recording_fields`' own
            # `None` placeholders for `_MEDIA_PROBE_OWNED_FIELDS`
            # (CP Plus's container never carries them -- see that
            # function's docstring) -- re-running enumeration (this
            # method backs the plain `GET /evidence/{id}/recordings`
            # route, which the frontend calls on every Evidence-tab
            # view, not just once) must never blindly overwrite an
            # already-extracted/-probed `Recording` row's real values
            # with those placeholders. Phase 24.1 root cause: this
            # silently discarded `extract_recording`'s own probed
            # width/height/fps/duration_ms the moment an officer next
            # opened the Evidence tab.
            for key, value in fields.items():
                if key in _MEDIA_PROBE_OWNED_FIELDS:
                    continue
                setattr(recording, key, value)
        db.commit()
        db.refresh(recording)

        EvidenceManager.confirm_vendor(
            db,
            evidence.id,
            vendor="CP Plus",
            identification_method=_CP_PLUS_IDENTIFICATION_METHOD,
            confidence=_CP_PLUS_VENDOR_CONFIDENCE,
        )

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

    @staticmethod
    def _try_hikvision_recording(db: Session, evidence: Evidence, reader: Any) -> Recording | None:
        """Try Hikvision's sidecar-log-confirmed exported-clip identification against `reader`.

        Unlike CP Plus, an exported Hikvision clip is already a standard,
        `ffprobe`-readable container -- so `fields` here carries REAL
        codec/container/width/height/fps/duration_ms values from a
        read-only probe of the immutable source file itself, not `None`
        placeholders (`app.adapters.hikvision.models.to_recording_fields`'
        own docstring). Every field is therefore always overwritten on
        update (no `_MEDIA_PROBE_OWNED_FIELDS` skip, unlike the CP Plus
        path above) -- re-probing this evidence's own unchanging source
        file is idempotent and, when it succeeds, always at least as
        authoritative as whatever was stored before; a failed re-probe
        (`value is None`) still never clobbers a previously-good value.

        Returns:
            The `Recording`, or `None` when this evidence is not a
            sidecar-log-confirmed Hikvision export.
        """
        enumeration = HikvisionParser(
            reader=reader, source_evidence_id=evidence.evidence_id
        ).enumerate_recordings()
        if (
            enumeration.status != HikvisionClipIdentificationStatus.CONFIRMED_BY_EXPORT_LOG
            or not enumeration.recordings
        ):
            return None

        hik_record = enumeration.recordings[0]
        fields = hikvision_to_recording_fields(hik_record)

        recording = (
            db.query(Recording).filter(Recording.recording_id == hik_record.recording_id).first()
        )
        if recording is None:
            recording = Recording(evidence_id=evidence.id, **fields)
            db.add(recording)
        else:
            for key, value in fields.items():
                if value is None and key in _MEDIA_PROBE_OWNED_FIELDS:
                    continue
                setattr(recording, key, value)
        db.commit()
        db.refresh(recording)

        EvidenceManager.confirm_vendor(
            db,
            evidence.id,
            vendor="Hikvision",
            identification_method=_HIKVISION_IDENTIFICATION_METHOD,
            confidence=hik_record.confidence,
        )

        RecordingManager._set_metadata(db, recording, "vendor", "Hikvision")
        RecordingManager._set_metadata(db, recording, "parser_version", hik_record.parser_version)
        RecordingManager._set_metadata(
            db, recording, "timestamp_source", hik_record.timestamp_source.value
        )
        sidecar = hik_record.identification.sidecar
        if sidecar is not None:
            if sidecar.device_serial is not None:
                RecordingManager._set_metadata(
                    db, recording, "hikvision_device_serial", sidecar.device_serial
                )
                EvidenceManager.confirm_device_serial(db, evidence.id, sidecar.device_serial)
            RecordingManager._set_metadata(
                db, recording, "hikvision_export_log_path", sidecar.source_path
            )
            if sidecar.export_timestamp is not None:
                RecordingManager._set_metadata(
                    db,
                    recording,
                    "hikvision_export_timestamp",
                    sidecar.export_timestamp.isoformat(),
                )
        known_device = hik_record.identification.known_device
        if known_device is not None:
            # Only ever set for this project's one examiner-confirmed
            # device serial -- see `HikvisionKnownDevice`'s own docstring.
            # Never inferred for a confirmed-but-unrecognized serial.
            RecordingManager._set_metadata(
                db, recording, "hikvision_device_model", known_device.model
            )
            RecordingManager._set_metadata(
                db, recording, "hikvision_device_firmware", known_device.firmware
            )
            RecordingManager._set_metadata(
                db, recording, "hikvision_device_timezone", known_device.timezone
            )
        if hik_record.has_audio is not None:
            RecordingManager._set_metadata(db, recording, "has_audio", str(hik_record.has_audio))
        if hik_record.audio_codec is not None:
            RecordingManager._set_metadata(db, recording, "audio_codec", hik_record.audio_codec)

        return recording

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
        RecordingManager._set_metadata(db, session_recording, "segment_count", str(len(segments)))
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

        vendor = (
            db.query(RecordingMetadata)
            .filter(
                RecordingMetadata.recording_id == recording.id, RecordingMetadata.key == "vendor"
            )
            .first()
        )
        if vendor is not None and vendor.value == "Hikvision":
            return RecordingManager._extract_hikvision_recording(db, recording)

        segments = RecordingManager._resolve_segments(db, recording)

        case = db.query(Case).filter(Case.id == recording.evidence.case_id).first()
        assert case is not None
        relative_dir = (
            f"{case.case_id}/{recording.evidence.evidence_id}/recordings/{recording.recording_id}"
        )
        elementary_stream_path = prepare_artifact_directory(
            f"{relative_dir}/elementary_stream.h265"
        )

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
    def _extract_hikvision_recording(db: Session, recording: Recording) -> Recording:
        """Extract one Hikvision exported-clip recording's playable output.

        Unlike CP Plus, an exported Hikvision clip is already a complete,
        standard container -- no elementary-stream reassembly step exists
        between the preserved evidence and FFmpeg.
        `app.media.decoder.remux_container_to_mp4`/
        `transcode_container_to_h264_aac_mp4` read directly from the
        preserved source evidence file (see those functions' own
        docstrings for why: FFmpeg's own demuxer already skips the file's
        leading "IMKH" header and correctly decodes the underlying
        MPEG-PS payload -- confirmed against real evidence).

        Args:
            db: Database session.
            recording: The `Recording` to extract. Its `vendor`
                `RecordingMetadata` entry must already be `"Hikvision"`
                (checked by the caller, `extract_recording`).

        Returns:
            The updated `Recording`. Never raises for an FFmpeg-side
            failure -- reported via `extraction_status`/
            `extraction_warnings` metadata instead, matching
            `extract_recording`'s own contract.

        Raises:
            ValueError: If the recording's source evidence cannot be
                resolved.
        """
        evidence = recording.evidence
        if evidence is None or not evidence.source_path:
            raise ValueError(
                f"Recording {recording.id}'s source evidence could not be resolved for extraction"
            )
        source_path = Path(evidence.source_path)

        case = db.query(Case).filter(Case.id == evidence.case_id).first()
        assert case is not None
        relative_dir = f"{case.case_id}/{evidence.evidence_id}/recordings/{recording.recording_id}"

        warnings: list[str] = []
        extraction_status = "successful"

        master_path = prepare_artifact_directory(f"{relative_dir}/master.mp4")
        mux_result = remux_container_to_mp4(source_path, master_path)
        master_artifact: Artifact | None = None
        if mux_result.ok:
            probe = probe_media(master_path)
            if probe.available:
                recording.codec = probe.codec
                recording.container = "mp4"
                recording.width = probe.width
                recording.height = probe.height
                recording.fps = probe.fps
                if probe.duration_seconds is not None:
                    recording.duration_ms = int(round(probe.duration_seconds * 1000))
                warnings.extend(probe.warnings)
            if mux_result.stderr.strip():
                # A non-fatal ffmpeg-side warning (e.g. a tolerated PS-packet
                # issue) can appear even on an otherwise-`ok` remux --
                # surfaced, never discarded.
                warnings.append(f"ffmpeg remux warning: {mux_result.stderr[-2000:]}")

            master_artifact = EvidenceManager.register_artifact(
                db,
                recording.evidence_id,
                ArtifactCreateRequest(
                    relative_path=f"{relative_dir}/master.mp4",
                    artifact_type="hikvision_export_master_mp4",
                    size_bytes=master_path.stat().st_size,
                    sha256=sha256_file(master_path),
                    md5=md5_file(master_path),
                    tool_version=get_ffmpeg_version(),
                ),
            )
            recording.artifact_id = str(master_artifact.id)
        else:
            extraction_status = "failed"
            warnings.append(f"ffmpeg remux to master MP4 failed: {mux_result.stderr[-2000:]}")

        preview_path = prepare_artifact_directory(f"{relative_dir}/preview_h264.mp4")
        transcode_result = transcode_container_to_h264_aac_mp4(source_path, preview_path)
        if transcode_result.ok:
            preview_artifact = EvidenceManager.register_artifact(
                db,
                recording.evidence_id,
                ArtifactCreateRequest(
                    relative_path=f"{relative_dir}/preview_h264.mp4",
                    artifact_type="hikvision_export_preview_mp4",
                    parent_artifact_id=master_artifact.id if master_artifact is not None else None,
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
            if extraction_status == "successful":
                extraction_status = "partial"
            warnings.append(
                f"ffmpeg transcode to H.264 preview MP4 failed: {transcode_result.stderr[-2000:]}"
            )

        db.commit()
        db.refresh(recording)

        RecordingManager._set_metadata(db, recording, "extraction_status", extraction_status)
        RecordingManager._set_metadata(db, recording, "extraction_warnings", json.dumps(warnings))
        ffmpeg_version = get_ffmpeg_version()
        if ffmpeg_version is not None:
            RecordingManager._set_metadata(db, recording, "ffmpeg_version", ffmpeg_version)

        db.commit()
        db.refresh(recording)
        return recording

    @staticmethod
    def refresh_media_metadata(db: Session, recording_id: int) -> Recording:
        """Re-probe this recording's already-produced derived media and
        persist the actual codec/container/width/height/fps/duration onto
        the `Recording` row.

        Purely a read-only `ffprobe` pass over an artifact that already
        exists on disk (task: "Use the existing recording/media probing
        infrastructure... Do NOT rewrite/transcode the master MP4"). This
        exists to backfill `Recording` rows whose technical metadata was
        never captured -- e.g. rows written before `extract_recording`
        tracked this metadata, or a recording whose HEVC master mux failed
        (see `_resolve_probeable_artifact`) but whose H.264 preview
        transcode still succeeded. Never re-extracts, re-muxes,
        re-transcodes, or touches source evidence/hashes/artifact rows;
        never fabricates a value `probe_media` did not itself return.

        Args:
            db: Database session.
            recording_id: Primary key of the `Recording` to refresh.

        Returns:
            The updated `Recording`. If probing fails/is unavailable, the
            existing fields are left untouched and the honest failure is
            recorded via `media_metadata_refresh_status`/`_warnings`
            metadata instead of raising.

        Raises:
            ValueError: If the recording is not found, or it has no
                derived master/preview media artifact at all yet to probe
                (extraction was never run for it).
        """
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            raise ValueError(f"Recording with id {recording_id} not found")

        artifact = RecordingManager._resolve_probeable_artifact(db, recording)
        if artifact is None:
            raise ValueError(
                f"Recording {recording_id} has no derived master/preview media artifact to "
                "probe -- run POST /recordings/{recording_id}/extract first"
            )

        probe = probe_media(Path(artifact.path))
        if not probe.available:
            RecordingManager._set_metadata(
                db, recording, "media_metadata_refresh_status", "unavailable"
            )
            RecordingManager._set_metadata(
                db, recording, "media_metadata_refresh_warnings", json.dumps(probe.warnings)
            )
            db.commit()
            db.refresh(recording)
            return recording

        recording.codec = probe.codec
        recording.container = "mp4"
        recording.width = probe.width
        recording.height = probe.height
        recording.fps = probe.fps
        if probe.duration_seconds is not None:
            recording.duration_ms = int(probe.duration_seconds * 1000)
        if artifact.artifact_type == RecordingManager._MASTER_ARTIFACT_TYPE and (
            recording.artifact_id != str(artifact.id)
        ):
            # Self-heals a `Recording` row whose `artifact_id` link to its
            # own master artifact was never set (or was stale) -- the
            # master artifact/file was resolved to exist, so future reads
            # of `Recording.artifact_id` reflect that too.
            recording.artifact_id = str(artifact.id)
        db.commit()
        db.refresh(recording)

        RecordingManager._set_metadata(db, recording, "media_metadata_refresh_status", "successful")
        RecordingManager._set_metadata(
            db, recording, "media_metadata_refreshed_from_artifact_id", str(artifact.id)
        )
        db.commit()
        db.refresh(recording)
        return recording

    #: `Artifact.artifact_type` for the un-transcoded, muxed-not-re-encoded
    #: HEVC master MP4 `extract_recording` produces -- the higher-fidelity
    #: derived file, preferred over the H.264 preview whenever one exists.
    _MASTER_ARTIFACT_TYPE = "cp_plus_hevc_master_mp4"

    @staticmethod
    def _resolve_probeable_artifact(db: Session, recording: Recording) -> Artifact | None:
        """The derived media artifact whose technical metadata best
        describes this recording: the un-transcoded HEVC master when one
        exists, else the H.264 preview (`preview_artifact_id` metadata) --
        whichever was actually produced. Prefers the master since it is
        the higher-fidelity, non-lossy-re-encoded derived file; falls back
        to the preview only when no master is available (either the mux
        genuinely failed -- a truncated segment can fail
        `mux_hevc_annexb_to_mp4` while the separate H.264 transcode still
        succeeds -- or, for a `Recording` row written before
        `extract_recording` started persisting `Recording.artifact_id`,
        that link is simply unset even though the master artifact/file
        genuinely exists; the `evidence_id`-scoped lookup below recovers
        it in that case too). Returns `None` (never guesses/fabricates a
        path) when no such artifact's row and on-disk file both exist.
        """
        if recording.artifact_id:
            artifact = db.query(Artifact).filter(Artifact.id == int(recording.artifact_id)).first()
            if artifact is not None and Path(artifact.path).is_file():
                return artifact

        master_artifact = (
            db.query(Artifact)
            .filter(
                Artifact.evidence_id == recording.evidence_id,
                Artifact.artifact_type == RecordingManager._MASTER_ARTIFACT_TYPE,
            )
            .order_by(Artifact.id.desc())
            .first()
        )
        if master_artifact is not None and Path(master_artifact.path).is_file():
            return master_artifact

        preview_entry = (
            db.query(RecordingMetadata)
            .filter(
                RecordingMetadata.recording_id == recording.id,
                RecordingMetadata.key == "preview_artifact_id",
            )
            .first()
        )
        if preview_entry is not None and preview_entry.value:
            artifact = db.query(Artifact).filter(Artifact.id == int(preview_entry.value)).first()
            if artifact is not None and Path(artifact.path).is_file():
                return artifact

        return None

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
