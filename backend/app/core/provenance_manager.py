"""
Business logic for provenance and chain-of-custody recording (Phase 15).
Master Specification Section 39 ("Provenance Engine"), Section 40
("Chain of Custody").

This is the DB-aware orchestration layer built on `app.audit.*` (the pure
vocabulary): `record_event` appends one immutable `ProcessingEvent` row;
the traversal methods are thin, read-only wrappers over the *existing*
`Artifact.parent_artifact_id`/`child_artifacts`/`evidence_id`
relationships (Phase 4) -- no new lineage storage. Confirmed by inspection
that `RecordingManager.extract_recording` (Phase 9) already sets
`parent_artifact_id` when registering derived artifacts, so this layer
only needs to walk what already exists.

`record_event` owns event *creation*; it never computes hash-chain
fields itself. Immediately after adding the row to the session, it
delegates to `app.core.audit_chain_manager.AuditChainManager.seal_event`
(Phase 16) to assign `previous_hash`/`current_hash` and commit -- a
single, sanctioned integration point. `AuditChainManager` never creates
a `ProcessingEvent` itself, so there is no competing event-recording
path and no circular import.

Never mutates a source evidence, artifact, recording, or timestamp row --
only reads them and appends new `ProcessingEvent` rows (never updates one
after creation: Master Specification Section 51 rule 5, "Audit/custody
events must be append-oriented"). Phase 15 does not reimplement
acquisition/parsing/extraction/recovery/AI/validation/correlation -- it
only records their history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.audit import ActorType
from app.core.audit_chain_manager import AuditChainManager
from app.models import Artifact, Case, Evidence, Job, JobStatus, ProcessingEvent

__all__ = ["CaseProvenanceSummary", "ProvenanceManager"]


@dataclass(frozen=True)
class CaseProvenanceSummary:
    """A lightweight observability summary for one case's processing history."""

    case_id: int
    processing_event_count: int
    artifact_count: int
    last_event: ProcessingEvent | None
    tools_used: list[str] = field(default_factory=list)


class ProvenanceManager:
    """Service layer for recording and querying processing/provenance history."""

    # ---- Recording ------------------------------------------------------

    @staticmethod
    def record_event(
        db: Session,
        *,
        case_id: int,
        operation: str,
        actor: str,
        actor_type: ActorType,
        status: JobStatus,
        evidence_id: int | None = None,
        job_id: int | None = None,
        tool: str | None = None,
        tool_version: str | None = None,
        software_version: str | None = None,
        parameters: dict[str, object] | None = None,
        input_artifact_ids: list[int] | None = None,
        output_artifact_ids: list[int] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        warnings: list[str] | None = None,
        error: str | None = None,
        notes: str | None = None,
        description: str | None = None,
        location_reference: str | None = None,
    ) -> ProcessingEvent:
        """Append one immutable processing-event record.

        Args:
            db: Database session.
            case_id: Primary key of the owning case. Must exist.
            operation: An `app.audit.events.ProcessingOperation` or
                `app.audit.chain_of_custody.CustodyEventType` value.
            actor: Who/what performed the operation (an examiner's name,
                or a machine/component identifier such as
                `"CPPlusParser"`/`"RecoveryEngine"`).
            actor_type: `ActorType.HUMAN` or `ActorType.SYSTEM` --
                required, never inferred (task Phase 15 scope section 5:
                "Never claim an automated process was performed by a
                human").
            status: The operation's real outcome. Never pass `COMPLETED`
                for a partially-succeeded operation -- use `PARTIAL`.
            evidence_id: The evidence this operation concerns, if any.
                Must exist and belong to `case_id`. `None` for case-scoped
                operations that span multiple evidence items (e.g.
                cross-camera correlation).
            job_id: Cross-reference to a `Job` row, if one exists for
                this operation (e.g. AI/validation jobs). Must exist.
            tool: Component/tool name (e.g. `"ffmpeg"`, `"CPPlusParser"`,
                `"yolov8n.pt"`).
            tool_version: The exact version used. Never `"latest"` when
                the real version is known.
            software_version: The 24FPS application version.
            parameters: Reproducibility parameters. Never secrets.
            input_artifact_ids: Artifacts this operation consumed. Every
                ID must reference a real `Artifact` row.
            output_artifact_ids: Artifacts this operation produced. Every
                ID must reference a real `Artifact` row.
            started_at: When the operation began.
            completed_at: When the operation finished.
            warnings: Non-fatal issues encountered.
            error: A summary error message, if the operation did not
                fully succeed.
            notes: Free-text notes.
            description: A human-readable summary (Master Specification
                Section 40's "description" field).
            location_reference: Physical/storage location context
                (Master Specification Section 40's "location/reference"
                field).

        Returns:
            The created, immutable `ProcessingEvent`, sealed into its
            case's hash-linked audit chain (Phase 16: `previous_hash`/
            `current_hash` are always set by the time this returns).

        Raises:
            ValueError: If `case_id`/`evidence_id`/`job_id` does not
                exist, if `evidence_id` does not belong to `case_id`, if
                any referenced artifact does not exist, or if any
                referenced artifact belongs to evidence outside the
                stated `evidence_id` (when given) or outside `case_id`'s
                own evidence (task Phase 15 scope section 28: cross-
                evidence safety -- never silently attach an artifact to
                the wrong evidence).
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if case is None:
            raise ValueError(f"Case with id {case_id} not found")

        if evidence_id is not None:
            evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
            if evidence is None:
                raise ValueError(f"Evidence with id {evidence_id} not found")
            if evidence.case_id != case_id:
                raise ValueError(f"Evidence {evidence_id} does not belong to case {case_id}")

        if job_id is not None and db.query(Job).filter(Job.id == job_id).first() is None:
            raise ValueError(f"Job with id {job_id} not found")

        referenced_ids = set(input_artifact_ids or []) | set(output_artifact_ids or [])
        if referenced_ids:
            found = {
                a.id: a for a in db.query(Artifact).filter(Artifact.id.in_(referenced_ids)).all()
            }
            missing = referenced_ids - found.keys()
            if missing:
                raise ValueError(f"referenced artifact(s) not found: {sorted(missing)}")
            for artifact_id, artifact in found.items():
                if evidence_id is not None and artifact.evidence_id != evidence_id:
                    raise ValueError(
                        f"artifact {artifact_id} belongs to evidence {artifact.evidence_id}, "
                        f"not the stated evidence {evidence_id}"
                    )
                if artifact.evidence.case_id != case_id:
                    raise ValueError(
                        f"artifact {artifact_id} belongs to a different case "
                        f"({artifact.evidence.case_id}), not case {case_id}"
                    )

        event = ProcessingEvent(
            case_id=case_id,
            evidence_id=evidence_id,
            job_id=job_id,
            operation=operation,
            actor=actor,
            actor_type=actor_type.value,
            tool=tool,
            tool_version=tool_version,
            software_version=software_version,
            parameters=json.dumps(parameters) if parameters is not None else None,
            input_artifact_ids=(
                json.dumps(input_artifact_ids) if input_artifact_ids is not None else None
            ),
            output_artifact_ids=(
                json.dumps(output_artifact_ids) if output_artifact_ids is not None else None
            ),
            started_at=started_at,
            completed_at=completed_at,
            status=status.value,
            warnings=json.dumps(warnings) if warnings is not None else None,
            error=error,
            notes=notes,
            description=description,
            location_reference=location_reference,
        )
        db.add(event)
        event = AuditChainManager.seal_event(db, event)
        return event

    # ---- Artifact lineage (reuses existing Artifact relationships) ------

    @staticmethod
    def get_artifact_source(db: Session, artifact_id: int) -> Evidence:
        """Return the evidence item that ultimately owns this artifact.

        `Artifact.evidence_id` is always set directly on every artifact
        (whether or not it also has a `parent_artifact_id`), so no
        traversal is needed.

        Raises:
            ValueError: If the artifact does not exist.
        """
        artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if artifact is None:
            raise ValueError(f"Artifact with id {artifact_id} not found")
        return artifact.evidence

    @staticmethod
    def get_artifact_ancestors(db: Session, artifact_id: int) -> list[Artifact]:
        """Return this artifact's ancestor chain, root-first.

        Walks `parent_artifact_id` from the given artifact up to the
        root (an artifact with no parent). Returns an empty list if the
        artifact has no parent.

        Raises:
            ValueError: If the artifact does not exist.
        """
        artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if artifact is None:
            raise ValueError(f"Artifact with id {artifact_id} not found")

        ancestors: list[Artifact] = []
        seen: set[int] = {artifact.id}
        current = artifact
        while current.parent_artifact_id is not None:
            parent = db.query(Artifact).filter(Artifact.id == current.parent_artifact_id).first()
            if parent is None or parent.id in seen:
                break
            ancestors.append(parent)
            seen.add(parent.id)
            current = parent
        ancestors.reverse()
        return ancestors

    @staticmethod
    def get_artifact_descendants(db: Session, artifact_id: int) -> list[Artifact]:
        """Return every artifact derived (directly or transitively) from this one.

        Raises:
            ValueError: If the artifact does not exist.
        """
        artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if artifact is None:
            raise ValueError(f"Artifact with id {artifact_id} not found")

        descendants: list[Artifact] = []
        seen: set[int] = set()
        queue: list[Artifact] = list(artifact.child_artifacts)
        while queue:
            current = queue.pop(0)
            if current.id in seen:
                continue
            seen.add(current.id)
            descendants.append(current)
            queue.extend(current.child_artifacts)
        return descendants

    # ---- Processing-event queries ---------------------------------------

    @staticmethod
    def get_processing_events_for_artifact(db: Session, artifact_id: int) -> list[ProcessingEvent]:
        """Find every recorded event that consumed or produced this artifact.

        Raises:
            ValueError: If the artifact does not exist.
        """
        artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if artifact is None:
            raise ValueError(f"Artifact with id {artifact_id} not found")

        candidates = (
            db.query(ProcessingEvent)
            .filter(ProcessingEvent.case_id == artifact.evidence.case_id)
            .order_by(ProcessingEvent.id)
            .all()
        )
        matches: list[ProcessingEvent] = []
        for event in candidates:
            inputs = json.loads(event.input_artifact_ids) if event.input_artifact_ids else []
            outputs = json.loads(event.output_artifact_ids) if event.output_artifact_ids else []
            if artifact_id in inputs or artifact_id in outputs:
                matches.append(event)
        return matches

    @staticmethod
    def get_case_history(db: Session, case_id: int) -> list[ProcessingEvent]:
        """List every recorded processing event for a case, in the order recorded."""
        return (
            db.query(ProcessingEvent)
            .filter(ProcessingEvent.case_id == case_id)
            .order_by(ProcessingEvent.id)
            .all()
        )

    @staticmethod
    def get_evidence_processing_events(db: Session, evidence_id: int) -> list[ProcessingEvent]:
        """List every recorded processing event scoped directly to one evidence item."""
        return (
            db.query(ProcessingEvent)
            .filter(ProcessingEvent.evidence_id == evidence_id)
            .order_by(ProcessingEvent.id)
            .all()
        )

    @staticmethod
    def get_case_summary(db: Session, case_id: int) -> CaseProvenanceSummary:
        """A lightweight observability summary: event/artifact counts, last
        event, and the distinct tools recorded for this case (task Phase
        15 scope section 34)."""
        events = ProvenanceManager.get_case_history(db, case_id)
        artifact_count = (
            db.query(Artifact)
            .join(Evidence, Artifact.evidence_id == Evidence.id)
            .filter(Evidence.case_id == case_id)
            .count()
        )
        tools = sorted({event.tool for event in events if event.tool is not None})
        return CaseProvenanceSummary(
            case_id=case_id,
            processing_event_count=len(events),
            artifact_count=artifact_count,
            last_event=events[-1] if events else None,
            tools_used=tools,
        )
