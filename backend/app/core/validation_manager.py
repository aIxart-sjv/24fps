"""
Business logic for ground truth and validation runs (Phase 14).
Master Specification Section 36 ("Validation Engine"), Section 37
("Ground-Truth Dataset Model").

This is the DB-aware orchestration layer built on `app.core.job_manager`
(generic job persistence, reused with `job_type="validation"`) and
`app.validation.*` (the pure metric engine): it loads independently-
supplied `GroundTruth` rows and the real, already-computed system output
(`AIResult`/`MotionEvent`/`AITrack`/`TimelineEvent`/`RecoveryResult`/
`Recording`) for a case, converts both to the pure dataclasses
`app.validation.*_metrics` expects, and persists the resulting
`ValidationMetric` rows.

Never mutates a source evidence, recording, timestamp, or AI-result row
-- only reads them and writes new `GroundTruth`/`ValidationMetric`/`Job`
rows (task Phase 14 scope section 33: "Validation must not modify:
original videos, CPV evidence, recovered source evidence, original
timestamps"). Ground truth is always independently supplied by the
caller -- no method here reads a system-output table and writes a
`GroundTruth` row from it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.ai.types import BoundingBox, Detection
from app.core.job_manager import JobManager
from app.models import (
    AIResult,
    AITrack,
    GroundTruth,
    Job,
    JobStatus,
    MotionEvent,
    Recording,
    RecoveryResult,
    TimelineEvent,
    ValidationMetric,
)
from app.validation import frame_metrics, motion_metrics, tracking_metrics
from app.validation.benchmark import (
    MetricRecord,
    ValidationType,
    metrics_from_counts,
    structural_check_metrics,
)
from app.validation.correlation_metrics import (
    DEFAULT_TIME_TOLERANCE_SECONDS,
    SystemSequenceEvent,
    SystemSequenceGroup,
    match_sequences,
)
from app.validation.ground_truth import (
    GroundTruthDetection,
    GroundTruthMotionEvent,
    GroundTruthRecoverySegment,
    GroundTruthSequence,
    GroundTruthSequenceEvent,
    GroundTruthTrack,
)
from app.validation.recovery_metrics import SystemRecoveryOutcome, compare_recovery
from app.validation.timestamp_metrics import compare_timestamp, evaluate_ordering

__all__ = ["VALIDATION_JOB_TYPE", "ValidationManager"]

VALIDATION_JOB_TYPE = "validation"


def _utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime to timezone-aware UTC, treating a naive value
    as already-UTC.

    SQLite round-trips `DateTime(timezone=True)` columns as naive (an
    established characteristic throughout this codebase, not a Phase 14
    defect) -- a `GroundTruth`/`MotionEvent`/`Recording`/`TimelineEvent`
    row read fresh from the database can come back naive while a value
    still held from before a `commit()` in the same session stays aware.
    Comparing the two directly raises `TypeError`. Every datetime this
    module reads from an ORM row and hands to a pure `app.validation.*`
    dataclass passes through here first, so comparisons downstream never
    see a mixed aware/naive pair.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class ValidationManager:
    """Service layer for creating ground truth and running validation."""

    # ---- Ground truth -----------------------------------------------

    @staticmethod
    def create_ground_truth(
        db: Session,
        *,
        case_id: int,
        dataset_id: str,
        event_type: str,
        recording_id: int | None = None,
        camera_id: str | None = None,
        object_class: str | None = None,
        timestamp: datetime | None = None,
        frame_number: int | None = None,
        bbox: BoundingBox | None = None,
        expected_start: datetime | None = None,
        expected_end: datetime | None = None,
        expected_duration_ms: int | None = None,
        expected_frames: int | None = None,
        expected_fragments: int | None = None,
        expected_hash: str | None = None,
        group_reference: str | None = None,
        source_reference: str | None = None,
        notes: str | None = None,
    ) -> GroundTruth:
        """Create one independently-supplied ground-truth record.

        Args:
            db: Database session.
            case_id: Primary key of the owning case.
            dataset_id: The scenario/experiment grouping key a later
                `run_validation` call references.
            event_type: One of `ValidationType`'s values.
            source_reference: How/by whom this fact was independently
                established (e.g. "examiner annotation", "controlled
                recording script") -- never "copied from AI output".
            (all other args map directly onto `GroundTruth` columns.)

        Returns:
            The created `GroundTruth` row.
        """
        row = GroundTruth(
            case_id=case_id,
            dataset_id=dataset_id,
            recording_id=recording_id,
            camera_id=camera_id,
            event_type=event_type,
            object_class=object_class,
            timestamp=timestamp,
            frame_number=frame_number,
            bbox_x_min=bbox.x_min if bbox is not None else None,
            bbox_y_min=bbox.y_min if bbox is not None else None,
            bbox_x_max=bbox.x_max if bbox is not None else None,
            bbox_y_max=bbox.y_max if bbox is not None else None,
            expected_start=expected_start,
            expected_end=expected_end,
            expected_duration_ms=expected_duration_ms,
            expected_frames=expected_frames,
            expected_fragments=expected_fragments,
            expected_hash=expected_hash,
            group_reference=group_reference,
            source_reference=source_reference,
            notes=notes,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def list_ground_truth(
        db: Session, case_id: int, dataset_id: str, *, event_type: str | None = None
    ) -> list[GroundTruth]:
        """List ground-truth rows for one dataset, optionally filtered by event type."""
        query = db.query(GroundTruth).filter(
            GroundTruth.case_id == case_id, GroundTruth.dataset_id == dataset_id
        )
        if event_type is not None:
            query = query.filter(GroundTruth.event_type == event_type)
        return query.order_by(GroundTruth.id).all()

    # ---- Validation runs ----------------------------------------------

    @staticmethod
    def run_validation(
        db: Session,
        *,
        case_id: int,
        validation_type: str,
        dataset_id: str,
        iou_threshold: float = frame_metrics.DEFAULT_IOU_THRESHOLD,
        require_class_match: bool = True,
        motion_overlap_threshold: float = motion_metrics.DEFAULT_TEMPORAL_OVERLAP_THRESHOLD,
        correlation_time_tolerance_seconds: float = DEFAULT_TIME_TOLERANCE_SECONDS,
        frame_overlap_tolerance: int = 0,
    ) -> tuple[Job, list[ValidationMetric]]:
        """Create and synchronously run one validation job.

        Args:
            db: Database session.
            case_id: Primary key of the owning case.
            validation_type: One of `ValidationType`'s values.
            dataset_id: The ground-truth dataset/scenario to validate
                against.
            iou_threshold: Object/face detection bounding-box match
                threshold.
            require_class_match: Whether object/face detection matching
                requires exact class agreement.
            motion_overlap_threshold: Motion-event temporal-IoU match
                threshold.
            correlation_time_tolerance_seconds: Correlation sequence
                per-event timestamp tolerance.
            frame_overlap_tolerance: Tracking frame-range overlap slack.

        Returns:
            `(job, metrics)` -- `job.status` is always terminal
            (`COMPLETED`/`PARTIAL`/`FAILED`); `COMPLETED` only when
            ground truth existed and every comparison completed without
            a warning.

        Raises:
            ValueError: If `validation_type` is not recognized.
        """
        try:
            v_type = ValidationType(validation_type)
        except ValueError as exc:
            raise ValueError(f"unrecognized validation_type: {validation_type!r}") from exc

        parameters: dict[str, object] = {
            "validation_type": v_type.value,
            "dataset_id": dataset_id,
            "iou_threshold": iou_threshold,
            "require_class_match": require_class_match,
            "motion_overlap_threshold": motion_overlap_threshold,
            "correlation_time_tolerance_seconds": correlation_time_tolerance_seconds,
            "frame_overlap_tolerance": frame_overlap_tolerance,
        }
        job = JobManager.create_job(
            db, case_id=case_id, job_type=VALIDATION_JOB_TYPE, parameters=parameters
        )
        job = JobManager.mark_running(db, job)

        ground_truth_rows = ValidationManager.list_ground_truth(
            db, case_id, dataset_id, event_type=v_type.value
        )
        if not ground_truth_rows and v_type != ValidationType.VENDOR_PARSER:
            job = JobManager.finish_job(
                db,
                job,
                status=JobStatus.FAILED,
                results_count=0,
                error=f"no ground truth found for dataset_id={dataset_id!r}, event_type={v_type.value!r}",
            )
            return job, []

        warnings: list[str] = []
        if v_type in (ValidationType.OBJECT_DETECTION, ValidationType.FACE_DETECTION):
            records = ValidationManager._run_detection_validation(
                db,
                case_id=case_id,
                ground_truth_rows=ground_truth_rows,
                validation_type=v_type,
                iou_threshold=iou_threshold,
                require_class_match=require_class_match,
                warnings=warnings,
            )
        elif v_type == ValidationType.MOTION:
            records = ValidationManager._run_motion_validation(
                db,
                case_id=case_id,
                ground_truth_rows=ground_truth_rows,
                overlap_threshold=motion_overlap_threshold,
                warnings=warnings,
            )
        elif v_type == ValidationType.TRACKING:
            records = ValidationManager._run_tracking_validation(
                db,
                case_id=case_id,
                ground_truth_rows=ground_truth_rows,
                frame_overlap_tolerance=frame_overlap_tolerance,
                warnings=warnings,
            )
        elif v_type == ValidationType.CORRELATION:
            records = ValidationManager._run_correlation_validation(
                db,
                case_id=case_id,
                ground_truth_rows=ground_truth_rows,
                time_tolerance_seconds=correlation_time_tolerance_seconds,
            )
        elif v_type == ValidationType.TIMELINE:
            records = ValidationManager._run_timeline_validation(
                db, case_id=case_id, ground_truth_rows=ground_truth_rows, warnings=warnings
            )
        elif v_type == ValidationType.RECOVERY:
            records = ValidationManager._run_recovery_validation(
                db, case_id=case_id, ground_truth_rows=ground_truth_rows, warnings=warnings
            )
        else:  # ValidationType.VENDOR_PARSER
            records = ValidationManager._run_vendor_parser_validation(
                db, case_id=case_id, ground_truth_rows=ground_truth_rows, warnings=warnings
            )

        metric_rows = [
            ValidationMetric(
                job_id=job.id,
                case_id=case_id,
                dataset_id=dataset_id,
                validation_type=v_type.value,
                metric_name=record.name,
                metric_value=record.value,
                numerator=record.numerator,
                denominator=record.denominator,
                threshold=record.threshold,
                notes=record.notes,
            )
            for record in records
        ]
        db.add_all(metric_rows)
        db.commit()
        for row in metric_rows:
            db.refresh(row)

        status = JobStatus.PARTIAL if warnings else JobStatus.COMPLETED
        job = JobManager.finish_job(
            db,
            job,
            status=status,
            results_count=len(metric_rows),
            warnings=warnings or None,
        )
        return job, metric_rows

    @staticmethod
    def list_validation_metrics(
        db: Session,
        case_id: int,
        *,
        job_id: int | None = None,
        validation_type: str | None = None,
    ) -> list[ValidationMetric]:
        """List persisted validation metrics for a case, optionally filtered."""
        query = db.query(ValidationMetric).filter(ValidationMetric.case_id == case_id)
        if job_id is not None:
            query = query.filter(ValidationMetric.job_id == job_id)
        if validation_type is not None:
            query = query.filter(ValidationMetric.validation_type == validation_type)
        return query.order_by(ValidationMetric.id).all()

    # ---- Per-type dispatch (private) -----------------------------------

    @staticmethod
    def _run_detection_validation(
        db: Session,
        *,
        case_id: int,
        ground_truth_rows: list[GroundTruth],
        validation_type: ValidationType,
        iou_threshold: float,
        require_class_match: bool,
        warnings: list[str],
    ) -> list[MetricRecord]:
        ground_truth = [
            GroundTruthDetection(
                class_name=row.object_class or "",
                bbox=BoundingBox(
                    x_min=row.bbox_x_min or 0.0,
                    y_min=row.bbox_y_min or 0.0,
                    x_max=row.bbox_x_max or 0.0,
                    y_max=row.bbox_y_max or 0.0,
                ),
                frame_number=row.frame_number,
                timestamp=_utc(row.timestamp),
            )
            for row in ground_truth_rows
        ]
        recording_ids = {
            row.recording_id for row in ground_truth_rows if row.recording_id is not None
        }
        if not recording_ids:
            warnings.append("no recording_id on ground truth rows; no system output to compare")

        predictions: list[Detection] = []
        if recording_ids:
            for ai_result in (
                db.query(AIResult)
                .filter(
                    AIResult.case_id == case_id,
                    AIResult.recording_id.in_(recording_ids),
                    AIResult.analysis_type == validation_type.value,
                )
                .all()
            ):
                predictions.append(
                    Detection(
                        class_name=ai_result.class_name,
                        confidence=ai_result.confidence,
                        bbox=BoundingBox(
                            x_min=ai_result.bbox_x_min,
                            y_min=ai_result.bbox_y_min,
                            x_max=ai_result.bbox_x_max,
                            y_max=ai_result.bbox_y_max,
                        ),
                        frame_number=ai_result.frame_number,
                        # `timestamp_seconds` is not used by matching (only
                        # class/bbox/frame_number are) and AIResult stores an
                        # absolute `timestamp`, not a relative offset -- 0.0
                        # is an explicit, documented, never-read placeholder.
                        timestamp_seconds=0.0,
                    )
                )

        match_result = frame_metrics.match_detections(
            ground_truth,
            predictions,
            iou_threshold=iou_threshold,
            require_class_match=require_class_match,
        )
        prefix = f"{validation_type.value}."
        records = metrics_from_counts(match_result.counts, prefix=prefix)
        records.append(MetricRecord(name=f"{prefix}iou_threshold", value=iou_threshold))
        return records

    @staticmethod
    def _run_motion_validation(
        db: Session,
        *,
        case_id: int,
        ground_truth_rows: list[GroundTruth],
        overlap_threshold: float,
        warnings: list[str],
    ) -> list[MetricRecord]:
        ground_truth: list[GroundTruthMotionEvent] = []
        for row in ground_truth_rows:
            start, end = _utc(row.expected_start), _utc(row.expected_end)
            if start is None or end is None:
                warnings.append(
                    f"ground_truth id={row.id}: missing expected_start/expected_end, skipped"
                )
                continue
            ground_truth.append(GroundTruthMotionEvent(start_time=start, end_time=end))

        recording_ids = {
            row.recording_id for row in ground_truth_rows if row.recording_id is not None
        }
        motion_event_rows = (
            db.query(MotionEvent)
            .filter(MotionEvent.case_id == case_id, MotionEvent.recording_id.in_(recording_ids))
            .all()
            if recording_ids
            else []
        )
        system_events: list[motion_metrics.SystemMotionEvent] = []
        for event in motion_event_rows:
            start, end = _utc(event.start_time), _utc(event.end_time)
            if start is None or end is None:
                continue
            system_events.append(motion_metrics.SystemMotionEvent(start_time=start, end_time=end))

        result = motion_metrics.match_motion_events(
            ground_truth, system_events, overlap_threshold=overlap_threshold
        )
        records = metrics_from_counts(result.counts, prefix="motion.")
        if result.matches:
            mean_start_error = sum(m.start_error_seconds for m in result.matches) / len(
                result.matches
            )
            mean_end_error = sum(m.end_error_seconds for m in result.matches) / len(result.matches)
            records.append(
                MetricRecord(name="motion.mean_start_error_seconds", value=mean_start_error)
            )
            records.append(MetricRecord(name="motion.mean_end_error_seconds", value=mean_end_error))
        return records

    @staticmethod
    def _run_tracking_validation(
        db: Session,
        *,
        case_id: int,
        ground_truth_rows: list[GroundTruth],
        frame_overlap_tolerance: int,
        warnings: list[str],
    ) -> list[MetricRecord]:
        records: list[MetricRecord] = []
        for row in ground_truth_rows:
            if row.recording_id is None:
                warnings.append(f"ground_truth id={row.id}: no recording_id, skipped")
                continue
            gt_track = GroundTruthTrack(
                class_name=row.object_class or "",
                first_seen_frame=row.frame_number or 0,
                last_seen_frame=(
                    row.expected_frames
                    if row.expected_frames is not None
                    else (row.frame_number or 0)
                ),
                expected_frame_count=row.expected_frames,
            )
            system_tracks = [
                tracking_metrics.SystemTrack(
                    class_name=track.class_name,
                    first_seen_frame=track.first_seen_frame,
                    last_seen_frame=track.last_seen_frame,
                    frame_count=track.frame_count,
                )
                for track in db.query(AITrack)
                .filter(AITrack.case_id == case_id, AITrack.recording_id == row.recording_id)
                .all()
            ]
            coverage = tracking_metrics.evaluate_track_continuity(
                gt_track, system_tracks, frame_overlap_tolerance=frame_overlap_tolerance
            )
            prefix = f"tracking.{row.group_reference or row.id}."
            records.append(
                MetricRecord(name=f"{prefix}coverage_fraction", value=coverage.coverage_fraction)
            )
            records.append(
                MetricRecord(
                    name=f"{prefix}fragmentation_count", value=float(coverage.fragmentation_count)
                )
            )
            records.append(
                MetricRecord(name=f"{prefix}missed_frames", value=float(coverage.missed_frames))
            )
            records.append(
                MetricRecord(
                    name=f"{prefix}class_match", value=1.0 if coverage.class_match else 0.0
                )
            )
        return records

    @staticmethod
    def _run_correlation_validation(
        db: Session,
        *,
        case_id: int,
        ground_truth_rows: list[GroundTruth],
        time_tolerance_seconds: float,
    ) -> list[MetricRecord]:
        sequences_by_group: dict[str, list[GroundTruth]] = {}
        for row in ground_truth_rows:
            key = row.group_reference or f"row-{row.id}"
            sequences_by_group.setdefault(key, []).append(row)

        ground_truth: list[GroundTruthSequence] = []
        for group_reference, rows in sequences_by_group.items():
            timed_rows: list[tuple[Any, datetime]] = []
            for row in rows:
                ts = _utc(row.timestamp)
                if ts is not None:
                    timed_rows.append((row, ts))
            timed_rows.sort(key=lambda pair: pair[1])
            events = [
                GroundTruthSequenceEvent(camera_id=row.camera_id or "", timestamp=ts)
                for row, ts in timed_rows
            ]
            ground_truth.append(GroundTruthSequence(group_reference=group_reference, events=events))

        system_groups: list[SystemSequenceGroup] = []
        for correlated_event in (
            db.query(TimelineEvent)
            .filter(
                TimelineEvent.case_id == case_id, TimelineEvent.event_type == "correlated_event"
            )
            .all()
        ):
            details: dict[str, Any] = (
                json.loads(correlated_event.description) if correlated_event.description else {}
            )
            member_ids = [int(eid) for eid in details.get("event_ids", [])]
            members = (
                db.query(TimelineEvent).filter(TimelineEvent.id.in_(member_ids)).all()
                if member_ids
                else []
            )
            system_events: list[SystemSequenceEvent] = []
            for member in members:
                ts = _utc(member.normalized_timestamp)
                if ts is None:
                    continue
                system_events.append(
                    SystemSequenceEvent(camera_id=member.camera_id or "", timestamp=ts)
                )
            system_groups.append(
                SystemSequenceGroup(correlation_id=str(correlated_event.id), events=system_events)
            )

        result = match_sequences(
            ground_truth, system_groups, time_tolerance_seconds=time_tolerance_seconds
        )
        records = metrics_from_counts(result.counts, prefix="correlation.")
        records.append(
            MetricRecord(name="correlation.time_tolerance_seconds", value=time_tolerance_seconds)
        )
        return records

    @staticmethod
    def _run_timeline_validation(
        db: Session, *, case_id: int, ground_truth_rows: list[GroundTruth], warnings: list[str]
    ) -> list[MetricRecord]:
        records: list[MetricRecord] = []
        errors: list[float] = []
        actual_by_id: dict[str, datetime | None] = {}
        expected_order: list[str] = []

        for row in ground_truth_rows:
            if row.recording_id is None or row.timestamp is None:
                warnings.append(f"ground_truth id={row.id}: missing recording_id/timestamp")
                continue
            recording = db.query(Recording).filter(Recording.id == row.recording_id).first()
            actual = _utc(recording.start_normalized) if recording is not None else None
            comparison = compare_timestamp(_utc(row.timestamp), actual)
            identifier = str(row.recording_id)
            expected_order.append(identifier)
            if actual is not None:
                actual_by_id[identifier] = actual
            if comparison.error_seconds is not None:
                errors.append(comparison.error_seconds)
                records.append(
                    MetricRecord(
                        name=f"timeline.error_seconds.recording_{row.recording_id}",
                        value=comparison.error_seconds,
                    )
                )
            else:
                warnings.append(f"recording {row.recording_id}: no normalized timestamp available")

        if errors:
            records.append(
                MetricRecord(
                    name="timeline.mean_absolute_error_seconds",
                    value=sum(abs(e) for e in errors) / len(errors),
                )
            )

        if len(expected_order) > 1:
            ordering = evaluate_ordering(expected_order, actual_by_id)
            records.append(
                MetricRecord(
                    name="timeline.ordering_correct",
                    value=(
                        (1.0 if ordering.correct else 0.0) if ordering.correct is not None else None
                    ),
                    notes=(
                        f"undetermined: missing timestamps for {ordering.missing_identifiers}"
                        if ordering.correct is None
                        else None
                    ),
                )
            )
        return records

    @staticmethod
    def _run_recovery_validation(
        db: Session, *, case_id: int, ground_truth_rows: list[GroundTruth], warnings: list[str]
    ) -> list[MetricRecord]:
        records: list[MetricRecord] = []
        for row in ground_truth_rows:
            if row.recording_id is None:
                warnings.append(f"ground_truth id={row.id}: no recording_id, skipped")
                continue
            recording = db.query(Recording).filter(Recording.id == row.recording_id).first()
            recovery_result = (
                db.query(RecoveryResult)
                .filter(RecoveryResult.recording_id == row.recording_id)
                .order_by(RecoveryResult.created_at.desc())
                .first()
            )
            gt_segment = GroundTruthRecoverySegment(
                expected_start=_utc(row.expected_start),
                expected_end=_utc(row.expected_end),
                expected_duration_ms=row.expected_duration_ms,
                expected_frames=row.expected_frames,
                expected_fragments=row.expected_fragments,
                expected_hash=row.expected_hash,
            )
            system_outcome = SystemRecoveryOutcome(
                status=recovery_result.status if recovery_result else None,
                actual_start=_utc(recording.start_original) if recording else None,
                actual_end=_utc(recording.end_original) if recording else None,
                actual_duration_ms=recording.duration_ms if recording else None,
                frames_recovered=recovery_result.frames_recovered if recovery_result else None,
                fragments_found=recovery_result.fragments_found if recovery_result else None,
                fragments_used=recovery_result.fragments_used if recovery_result else None,
                recovery_rate=recovery_result.recovery_rate if recovery_result else None,
                frame_continuity=recovery_result.frame_continuity if recovery_result else None,
                actual_hash=None,
            )
            if recovery_result is None:
                warnings.append(f"recording {row.recording_id}: no RecoveryResult found")
            comparison = compare_recovery(gt_segment, system_outcome)
            prefix = f"recovery.recording_{row.recording_id}."
            for name, value in (
                ("start_error_seconds", comparison.start_error_seconds),
                ("end_error_seconds", comparison.end_error_seconds),
                ("duration_error_ms", comparison.duration_error_ms),
                ("frames_error", comparison.frames_error),
                ("fragments_error", comparison.fragments_error),
            ):
                if value is not None:
                    records.append(MetricRecord(name=f"{prefix}{name}", value=float(value)))
            if comparison.hash_matches is not None:
                records.append(
                    MetricRecord(
                        name=f"{prefix}hash_matches", value=1.0 if comparison.hash_matches else 0.0
                    )
                )
            records.append(
                MetricRecord(
                    name=f"{prefix}status",
                    value=None,
                    notes=f"expected recovery ground truth vs actual status={system_outcome.status!r}",
                )
            )
        return records

    @staticmethod
    def _run_vendor_parser_validation(
        db: Session, *, case_id: int, ground_truth_rows: list[GroundTruth], warnings: list[str]
    ) -> list[MetricRecord]:
        recording_ids = {
            row.recording_id for row in ground_truth_rows if row.recording_id is not None
        }
        if not recording_ids:
            warnings.append("no recording_id on vendor_parser ground truth rows")
            return []

        records: list[MetricRecord] = []
        for recording_id in recording_ids:
            recording = db.query(Recording).filter(Recording.id == recording_id).first()
            checks = {
                "file_recognized": recording is not None,
                "recording_enumerated": recording is not None,
                "extraction_compatible": bool(recording and recording.artifact_id is not None),
            }
            records.extend(
                structural_check_metrics(checks, prefix=f"vendor_parser.recording_{recording_id}.")
            )
        return records
