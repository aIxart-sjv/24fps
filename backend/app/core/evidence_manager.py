"""
Business logic for evidence management.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.acquisition import open_reader
from app.acquisition.native_export import NATIVE_EXPORT_SOURCE_TYPE
from app.config import get_settings
from app.detection import identify_evidence
from app.hashing.md5 import md5_file
from app.hashing.sha256 import sha256_file
from app.models import Artifact, Case, Device, Evidence, Storage
from app.schemas.acquisition import NativeExportRegisterRequest
from app.schemas.artifact import ArtifactCreateRequest
from app.schemas.device import DeviceIdentificationResult
from app.schemas.evidence import EvidenceCreateRequest
from app.storage.artifact_store import prepare_artifact_directory
from app.utils.paths import resolve_evidence_source_path


class EvidenceManager:
    """Service layer for evidence registration and management."""

    @staticmethod
    def register_evidence(db: Session, case_id: int, request: EvidenceCreateRequest) -> Evidence:
        """Register new evidence in a case.

        Args:
            db: Database session.
            case_id: Case primary key.
            request: Evidence creation request.

        Returns:
            The created Evidence ORM object.

        Raises:
            ValueError: If evidence_id is not unique, the case is not found,
                or a supplied source path is unsafe.
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case with id {case_id} not found")

        existing = db.query(Evidence).filter(Evidence.evidence_id == request.evidence_id).first()
        if existing:
            raise ValueError(f"Evidence with evidence_id {request.evidence_id!r} already exists")

        source_path: str | None = None
        if request.source_path is not None:
            source_path = str(
                resolve_evidence_source_path(request.source_path, get_settings().evidence_root)
            )

        evidence = Evidence(
            evidence_id=request.evidence_id,
            case_id=case_id,
            source_type=request.source_type,
            source_path=source_path,
            source_description=request.source_description,
            status="registered",
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        return evidence

    @staticmethod
    def get_evidence(db: Session, evidence_id: int) -> Evidence | None:
        """Retrieve evidence by primary key.

        Args:
            db: Database session.
            evidence_id: Evidence primary key.

        Returns:
            The Evidence object or None if not found.
        """
        return db.query(Evidence).filter(Evidence.id == evidence_id).first()

    @staticmethod
    def get_evidence_by_evidence_id(db: Session, evidence_id: str) -> Evidence | None:
        """Retrieve evidence by evidence_id identifier.

        Args:
            db: Database session.
            evidence_id: Evidence identifier string.

        Returns:
            The Evidence object or None if not found.
        """
        return db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()

    @staticmethod
    def list_case_evidence(
        db: Session, case_id: int, skip: int = 0, limit: int = 100
    ) -> list[Evidence]:
        """List all evidence items in a case.

        Args:
            db: Database session.
            case_id: Case primary key.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of Evidence objects.
        """
        return (
            db.query(Evidence).filter(Evidence.case_id == case_id).offset(skip).limit(limit).all()
        )

    @staticmethod
    def register_artifact(
        db: Session, evidence_id: int, request: ArtifactCreateRequest
    ) -> Artifact:
        """Register a derived artifact produced from a registered evidence item.

        Resolves `request.relative_path` strictly inside ARTIFACT_ROOT (never
        the preserved evidence root) before creating the database row, and
        prepares the artifact's destination directory so a later-phase
        component can write the artifact's bytes into it. This method never
        writes the artifact file itself.

        Args:
            db: Database session.
            evidence_id: Primary key of the parent evidence item.
            request: Artifact creation request.

        Returns:
            The created Artifact ORM object.

        Raises:
            ValueError: If the evidence is not found, a supplied
                parent_artifact_id does not belong to the same evidence
                item, the resolved path already has a registered artifact,
                or `relative_path` is unsafe (traversal, symlink escape, or
                overlap with EVIDENCE_ROOT).
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence with id {evidence_id} not found")

        if request.parent_artifact_id is not None:
            parent = (
                db.query(Artifact)
                .filter(
                    Artifact.id == request.parent_artifact_id,
                    Artifact.evidence_id == evidence_id,
                )
                .first()
            )
            if not parent:
                raise ValueError(
                    f"parent_artifact_id {request.parent_artifact_id} does not reference an "
                    f"artifact belonging to evidence {evidence_id}"
                )

        resolved_path = prepare_artifact_directory(request.relative_path)

        existing = db.query(Artifact).filter(Artifact.path == str(resolved_path)).first()
        if existing:
            raise ValueError(f"An artifact is already registered at path {resolved_path}")

        artifact = Artifact(
            evidence_id=evidence_id,
            parent_artifact_id=request.parent_artifact_id,
            artifact_type=request.artifact_type,
            path=str(resolved_path),
            size_bytes=request.size_bytes,
            sha256=request.sha256,
            md5=request.md5,
            created_by=request.created_by,
            tool_version=request.tool_version,
            status=request.status,
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        return artifact

    @staticmethod
    def list_evidence_artifacts(db: Session, evidence_id: int) -> list[Artifact]:
        """List all derived artifacts registered against an evidence item.

        Args:
            db: Database session.
            evidence_id: Evidence primary key.

        Returns:
            List of Artifact objects, empty if none registered.

        Raises:
            ValueError: If evidence is not found.
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence with id {evidence_id} not found")
        return db.query(Artifact).filter(Artifact.evidence_id == evidence_id).all()

    @staticmethod
    def register_native_export(
        db: Session, case_id: int, request: NativeExportRegisterRequest
    ) -> Evidence:
        """Register a native DVR/NVR export as evidence (Master Spec Section 9, Path 1).

        A thin, semantically-pinned wrapper around `register_evidence`: it
        forces `source_type` to `"native_export"` so callers cannot
        register a native export under an inconsistent type, and goes
        through the exact same root-bound, read-only source validation
        every other evidence path uses. No vendor-specific parsing of the
        export's contents happens here — that is Phase 6+ scope.

        Args:
            db: Database session.
            case_id: Case primary key.
            request: Native-export registration request.

        Returns:
            The created Evidence ORM object.

        Raises:
            ValueError: If evidence_id is not unique, the case is not
                found, or the supplied source path is unsafe.
        """
        return EvidenceManager.register_evidence(
            db,
            case_id,
            EvidenceCreateRequest(
                evidence_id=request.evidence_id,
                source_type=NATIVE_EXPORT_SOURCE_TYPE,
                source_path=request.source_path,
                source_description=request.source_description,
            ),
        )

    @staticmethod
    def record_acquisition_metadata(
        db: Session, evidence_id: int, *, tool_version: str | None = None
    ) -> Artifact:
        """Capture acquisition-time metadata for a registered evidence item.

        Opens the evidence's registered source through the
        `EvidenceStorageReader` matching its declared `source_type` (chosen
        by `app.acquisition.open_reader` — never by inspecting file bytes;
        format/vendor identification is Phase 6+), records what the reader
        can determine about it (size, format, sector size, any embedded
        provenance hash values), and writes that as a JSON manifest
        artifact under ARTIFACT_ROOT through the Phase 4 artifact
        infrastructure (Master Specification Section 12: "preserve
        acquisition metadata separately"). The source evidence file itself
        is never written to.

        Args:
            db: Database session.
            evidence_id: Primary key of the evidence to describe.
            tool_version: Optional software version to record on the
                artifact.

        Returns:
            The created Artifact row for the acquisition manifest.

        Raises:
            ValueError: If evidence is not found, has no source_path, its
                owning case cannot be found, or a manifest is already
                registered at the resolved path.
            app.acquisition.e01_handler.E01UnavailableError: If the
                evidence is declared `"e01"` and `pyewf` is not installed.
            app.acquisition.e01_handler.E01FormatError: If the evidence is
                declared `"e01"` but does not carry a valid signature.
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence with id {evidence_id} not found")
        if not evidence.source_path:
            raise ValueError(f"Evidence with id {evidence_id} has no source_path to describe")

        case = db.query(Case).filter(Case.id == evidence.case_id).first()
        if not case:
            raise ValueError(f"Case for evidence {evidence_id} not found")

        reader = open_reader(evidence.source_type, Path(evidence.source_path))
        try:
            reader_metadata = reader.metadata()
            embedded_hashes = reader.hash()
        finally:
            reader.close()

        manifest: dict[str, Any] = {
            "evidence_id": evidence.evidence_id,
            "source_type": evidence.source_type,
            "source_path": evidence.source_path,
            "reader_metadata": reader_metadata,
            "embedded_hash_values": embedded_hashes,
            "generated_at": datetime.now(UTC).isoformat(),
            "software_version": get_settings().app_version,
        }

        relative_path = f"{case.case_id}/{evidence.evidence_id}/acquisition/manifest.json"
        manifest_path = prepare_artifact_directory(relative_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        return EvidenceManager.register_artifact(
            db,
            evidence_id,
            ArtifactCreateRequest(
                relative_path=relative_path,
                artifact_type="acquisition_manifest",
                size_bytes=manifest_path.stat().st_size,
                sha256=sha256_file(manifest_path),
                md5=md5_file(manifest_path),
                tool_version=tool_version,
                status="registered",
            ),
        )

    @staticmethod
    def identify_device(db: Session, evidence_id: int) -> tuple[Device, DeviceIdentificationResult]:
        """Run Phase 6 device identification and persist the result onto `Device`.

        Runs `app.detection.identify_evidence` (strictly read-only; opens
        the source only through the Phase 5 reader abstraction) and
        upserts the `Device` row for this evidence with whatever subset of
        the result has a home there (`vendor`/`model`/`firmware`/
        `serial_number`/`device_type`/`confidence`/`identification_method`).
        The richer result (`status`, `warnings`, `supporting_evidence`,
        `parser_selection_hints`) is not persisted — it is returned
        directly, per Master Specification Section 51 (no speculative
        columns/tables for fields the documented schema doesn't define a
        home for).

        Safe to call more than once: re-running identification updates the
        existing `Device` row rather than rejecting a duplicate.

        Args:
            db: Database session.
            evidence_id: Primary key of the evidence to identify.

        Returns:
            The persisted `Device` row and the full `DeviceIdentificationResult`.

        Raises:
            ValueError: If evidence is not found or has no source_path.
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence with id {evidence_id} not found")
        if not evidence.source_path:
            raise ValueError(f"Evidence with id {evidence_id} has no source_path to identify")

        result = identify_evidence(evidence.source_type, Path(evidence.source_path))

        device = db.query(Device).filter(Device.evidence_id == evidence_id).first()
        if device is None:
            device = Device(evidence_id=evidence_id)
            db.add(device)

        device.vendor = result.vendor
        device.model = result.model
        device.firmware = result.firmware
        device.serial_number = result.serial_number
        device.device_type = result.device_type
        device.confidence = result.confidence
        device.identification_method = result.identification_method

        db.commit()
        db.refresh(device)
        return device, result

    @staticmethod
    def confirm_vendor(
        db: Session,
        evidence_id: int,
        *,
        vendor: str,
        identification_method: str,
        confidence: float,
    ) -> Device:
        """Upsert vendor-confirmation fields onto `Device` from a
        vendor-specific manager's own positive structure match -- stronger,
        vendor-specific evidence than `identify_device`'s generic
        container/filesystem-signature tiers can ever produce (Master
        Specification Section 76 rule 6: `app.detection.device_identifier`
        deliberately never guesses a vendor).

        Called once a vendor-specific parser (currently only
        `RecordingManager`, for CP Plus) has positively confirmed evidence
        matches that vendor's own documented recording structure -- e.g. a
        recognized CPV/ADIT-v1 container, not merely a plausible
        `source_type` declaration (task Phase 24 scope, "Acquisition
        Metadata -- Fix Accuracy": "For real CP Plus evidence, use the
        strongest actual evidence available: recognized CPV structure").

        Only overwrites `vendor`/`identification_method`/`confidence`;
        every other `Device` field (`model`/`firmware`/`serial_number`/
        `device_type`) is left exactly as `identify_device` (or a prior
        call to this method) set it, since a structure match alone does
        not determine those.

        Idempotent, matching `identify_device`'s own established pattern:
        safe to call more than once (e.g. on reprocessing) against the
        same evidence.
        """
        device = db.query(Device).filter(Device.evidence_id == evidence_id).first()
        if device is None:
            device = Device(evidence_id=evidence_id)
            db.add(device)
        device.vendor = vendor
        device.identification_method = identification_method
        device.confidence = confidence
        db.commit()
        db.refresh(device)
        return device

    @staticmethod
    def confirm_device_serial(db: Session, evidence_id: int, serial_number: str) -> Device:
        """Upsert `Device.serial_number` from a vendor-specific parser's own
        positive identification (Phase 26).

        Mirrors `confirm_vendor`'s established pattern (called once a
        vendor-specific parser -- currently `RecordingManager`, for
        Hikvision's export-log-sidecar-confirmed clips -- has positively
        read a device serial number from real evidence, stronger than
        `identify_device`'s generic container/filesystem tiers can ever
        produce), but touches only `serial_number`, never `vendor`/
        `identification_method`/`confidence` (those remain
        `confirm_vendor`'s own responsibility, called separately).

        Idempotent, matching `identify_device`/`confirm_vendor`: safe to
        call more than once against the same evidence.

        Args:
            db: Database session.
            evidence_id: Primary key of the evidence this serial number was
                read from.
            serial_number: The device serial number, read verbatim from
                real evidence (e.g. a device export-log sidecar) -- never
                guessed.

        Returns:
            The persisted `Device` row.
        """
        device = db.query(Device).filter(Device.evidence_id == evidence_id).first()
        if device is None:
            device = Device(evidence_id=evidence_id)
            db.add(device)
        device.serial_number = serial_number
        db.commit()
        db.refresh(device)
        return device

    @staticmethod
    def detect_format(db: Session, evidence_id: int) -> tuple[Storage, DeviceIdentificationResult]:
        """Run Phase 6 storage/format identification and persist onto `Storage`.

        Runs the same `app.detection.identify_evidence` pass as
        `identify_device` and upserts the `Storage` row with the subset
        that has a home there (`capacity_bytes`/`sector_size`/
        `image_format`/`image_path`/`read_only`/`status`).
        `manufacturer`/`model`/`serial_number`/`interface` are physical-
        media facts this module has no way to determine from file
        inspection and are left unset rather than fabricated.

        Safe to call more than once, matching `identify_device`.

        Args:
            db: Database session.
            evidence_id: Primary key of the evidence to inspect.

        Returns:
            The persisted `Storage` row and the full `DeviceIdentificationResult`.

        Raises:
            ValueError: If evidence is not found or has no source_path.
        """
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence with id {evidence_id} not found")
        if not evidence.source_path:
            raise ValueError(f"Evidence with id {evidence_id} has no source_path to inspect")

        result = identify_evidence(evidence.source_type, Path(evidence.source_path))

        storage = db.query(Storage).filter(Storage.evidence_id == evidence_id).first()
        if storage is None:
            storage = Storage(evidence_id=evidence_id)
            db.add(storage)

        storage.capacity_bytes = result.capacity
        storage.sector_size = result.sector_size
        storage.image_format = result.storage_format
        storage.image_path = evidence.source_path
        storage.read_only = True
        storage.status = result.status.value

        db.commit()
        db.refresh(storage)
        return storage, result
