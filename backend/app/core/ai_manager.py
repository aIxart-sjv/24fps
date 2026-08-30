"""
Business logic for running AI analysis jobs (Phase 13).
Master Specification Section 30-35 ("AI Backend" through "AI Processing
Jobs").

This is the DB-aware orchestration layer built on `app.core.job_manager`
(generic job persistence) and `app.ai.*` (the pure detection/tracking/
motion engine): it resolves each requested `Recording`'s already-produced
derived-MP4 artifact (Phase 9 output -- never reopens the proprietary CPV
format itself), decodes/samples frames via OpenCV, runs the requested
analysis types, and persists `AIResult`/`AITrack`/`MotionEvent` rows, all
linked back to the job and to the exact source artifact used (Master
Specification Section 51 rule 7).

Synchronous by design (task Phase 13 scope's own scoping note, matching
every prior phase's pattern -- Phase 9-12 all do their "long-running" work
inside a single manager call, and no background/thread-pool executor
exists anywhere in this codebase): `run_job` creates the `Job` row and
processes it to completion in the same call, transitioning PENDING ->
RUNNING -> COMPLETED/PARTIAL/FAILED with real timestamps. Fully callable
without HTTP.
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
from sqlalchemy.orm import Session

from app.ai.device import select_device
from app.ai.face_detection import detect_faces
from app.ai.frame_redundancy import (
    FrameRedundancyConfig,
    FrameRedundancyStats,
    aggregate_stats as aggregate_frame_redundancy_stats,
    evaluate_redundancy_sequence,
    summarize as summarize_frame_redundancy,
)
from app.ai.frame_sampling import SamplingStrategy, select_frames
from app.ai.model_registry import (
    ModelLoadResult,
    load_face_detection_model,
    load_object_detection_model,
)
from app.ai.motion_detection import METHOD_NAME as MOTION_METHOD_NAME
from app.ai.motion_detection import (
    DEFAULT_MIN_AREA,
    DEFAULT_THRESHOLD,
    detect_motion_events,
)
from app.ai.object_detection import detect_objects
from app.ai.tracking import BYTETRACK_TRACKER, run_tracking
from app.ai.types import AnalysisType, Detection, MotionEventResult, Track
from app.config import get_settings
from app.core.job_manager import JobManager
from app.models import (
    AI_JOB_TYPE,
    AIResult,
    AITrack,
    Artifact,
    Job,
    JobStatus,
    MotionEvent,
    Recording,
    RecordingMetadata,
)

__all__ = ["AIManager"]

_PREVIEW_ARTIFACT_METADATA_KEY = "preview_artifact_id"

_MODEL_LOADING_ANALYSIS_TYPES = frozenset(
    {AnalysisType.OBJECT_DETECTION, AnalysisType.OBJECT_TRACKING}
)

#: Default grayscale mean-absolute-difference threshold (0-255 scale) for
#: frame-redundancy evaluation (Phase 21, Part B) -- deliberately
#: conservative (a small, real change already exceeds it) since a
#: false-positive skip of meaningful evidence is unacceptable while a
#: false-negative (an unnecessary extra analysis) only costs compute.
#: Always recorded on `Job.parameters`, never silently applied.
DEFAULT_FRAME_REDUNDANCY_THRESHOLD = 3.0

#: A frame's timestamp gap from the reference frame beyond this many
#: multiples of the job's own actual sampling interval is treated as a
#: possible seek/discontinuity (`AnalyzeReason.TIMESTAMP_DISCONTINUITY`)
#: rather than an ordinary consecutive sampled frame. A multiplier of the
#: job's real interval, not a fixed number of seconds, so it scales
#: correctly whether the job sampled at 1 fps or 30 fps.
_TIMESTAMP_DISCONTINUITY_INTERVAL_MULTIPLIER = 5.0


class AIManager:
    """Service layer for running and querying AI analysis jobs."""

    @staticmethod
    def run_job(
        db: Session,
        *,
        case_id: int,
        recording_ids: list[int],
        analysis_types: list[str],
        sampling_strategy: str = SamplingStrategy.FPS.value,
        sampling_value: float | None = None,
        confidence_threshold: float = 0.25,
        face_confidence_threshold: float = 0.6,
        classes: list[str] | None = None,
        tracker: str = BYTETRACK_TRACKER,
        prefer_gpu: bool = True,
        frame_redundancy_enabled: bool = False,
        frame_redundancy_threshold: float = DEFAULT_FRAME_REDUNDANCY_THRESHOLD,
        frame_redundancy_max_skip_run: int | None = None,
    ) -> Job:
        """Create and synchronously run one AI analysis job.

        Args:
            db: Database session.
            case_id: Primary key of the owning case.
            recording_ids: Recordings to process. Every ID is recorded on
                the job even if a given recording later turns out to be
                missing/unusable -- that is reported as a warning, not
                silently dropped from the request record.
            analysis_types: Any of `AnalysisType`'s values.
            sampling_strategy: `SamplingStrategy` value (`"fps"`,
                `"interval"`, or `"all"`).
            sampling_value: Strategy-specific parameter. See
                `app.ai.frame_sampling.select_frames`.
            confidence_threshold: Minimum object-detection/tracking
                confidence to keep.
            face_confidence_threshold: Minimum face-detection score to
                keep.
            classes: Optional object-class allow-list.
            tracker: `app.ai.tracking.BYTETRACK_TRACKER` or `BOTSORT_TRACKER`.
            prefer_gpu: Use CUDA if available.
            frame_redundancy_enabled: If `True`, skip object/face-
                detection model inference on frames deemed redundant by
                `app.ai.frame_redundancy` (Phase 21, Part B). Never
                affects `OBJECT_TRACKING`/`MOTION_DETECTION`, which
                always see every one of their own sampled frames --
                see `app.ai.frame_redundancy`'s module docstring.
                Defaults to `False`: existing behavior (every sampled
                frame analyzed) is unchanged unless a caller opts in.
            frame_redundancy_threshold: See
                `app.ai.frame_redundancy.FrameRedundancyConfig.threshold`.
            frame_redundancy_max_skip_run: See
                `app.ai.frame_redundancy.FrameRedundancyConfig.max_skip_run`.

        Returns:
            The finished `Job` (`COMPLETED`, `PARTIAL`, or `FAILED`).

        Raises:
            ValueError: If `recording_ids` is empty or `analysis_types`
                contains an unrecognized value -- a bad request, checked
                before any `Job` row is created.
        """
        if not recording_ids:
            raise ValueError("recording_ids must not be empty")
        try:
            requested_types = [AnalysisType(value) for value in analysis_types]
        except ValueError as exc:
            raise ValueError(f"unrecognized analysis type in {analysis_types!r}: {exc}") from exc
        if not requested_types:
            raise ValueError("analysis_types must not be empty")

        parameters: dict[str, object] = {
            "sampling_strategy": sampling_strategy,
            "sampling_value": sampling_value,
            "confidence_threshold": confidence_threshold,
            "face_confidence_threshold": face_confidence_threshold,
            "classes": classes,
            "tracker": tracker,
            "prefer_gpu": prefer_gpu,
            "frame_redundancy_enabled": frame_redundancy_enabled,
            "frame_redundancy_threshold": frame_redundancy_threshold,
            "frame_redundancy_max_skip_run": frame_redundancy_max_skip_run,
        }

        job = JobManager.create_job(
            db,
            case_id=case_id,
            job_type=AI_JOB_TYPE,
            recording_ids=recording_ids,
            analysis_types=[t.value for t in requested_types],
            parameters=parameters,
        )
        job = JobManager.mark_running(db, job)

        device = select_device(prefer_gpu=prefer_gpu)
        model_root = get_settings().ai_model_root

        warnings: list[str] = []
        model_versions: dict[str, str] = {}
        unavailable_types: set[AnalysisType] = set()

        object_model: ModelLoadResult | None = None
        if _MODEL_LOADING_ANALYSIS_TYPES & set(requested_types):
            object_model = load_object_detection_model(model_root, device=device)
            if object_model.available:
                model_versions[object_model.model_name] = object_model.model_version
            else:
                warnings.append(f"object detection model unavailable: {object_model.error}")
                unavailable_types.update(_MODEL_LOADING_ANALYSIS_TYPES & set(requested_types))

        face_model: ModelLoadResult | None = None
        if AnalysisType.FACE_DETECTION in requested_types:
            face_model = load_face_detection_model(model_root)
            if face_model.available:
                model_versions[face_model.model_name] = face_model.model_version
            else:
                warnings.append(f"face detection model unavailable: {face_model.error}")
                unavailable_types.add(AnalysisType.FACE_DETECTION)

        results_count = 0
        recordings_succeeded = 0
        recordings_failed = 0
        redundancy_stats_by_recording: list[FrameRedundancyStats] = []

        for recording_id in recording_ids:
            outcome_warnings, outcome_results, redundancy_stats = AIManager._process_recording(
                db,
                job=job,
                case_id=case_id,
                recording_id=recording_id,
                requested_types=[t for t in requested_types if t not in unavailable_types],
                object_model=object_model,
                face_model=face_model,
                device=device,
                sampling_strategy=sampling_strategy,
                sampling_value=sampling_value,
                confidence_threshold=confidence_threshold,
                face_confidence_threshold=face_confidence_threshold,
                classes=classes,
                tracker=tracker,
                frame_redundancy_enabled=frame_redundancy_enabled,
                frame_redundancy_threshold=frame_redundancy_threshold,
                frame_redundancy_max_skip_run=frame_redundancy_max_skip_run,
            )
            warnings.extend(outcome_warnings)
            results_count += outcome_results
            if redundancy_stats is not None:
                redundancy_stats_by_recording.append(redundancy_stats)
            if outcome_results > 0 or not outcome_warnings:
                recordings_succeeded += 1
            else:
                recordings_failed += 1

        if recordings_succeeded == 0 and recording_ids:
            status = JobStatus.FAILED
            error = "; ".join(warnings) if warnings else "no recordings could be processed"
        elif recordings_failed > 0 or unavailable_types:
            status = JobStatus.PARTIAL
            error = None
        else:
            status = JobStatus.COMPLETED
            error = None

        if redundancy_stats_by_recording:
            aggregated = aggregate_frame_redundancy_stats(redundancy_stats_by_recording)
            if aggregated is not None:
                parameters["frame_redundancy_stats"] = aggregated.as_dict()
                job.parameters = json.dumps(parameters)
                db.add(job)

        return JobManager.finish_job(
            db,
            job,
            status=status,
            worker=device,
            model_versions=model_versions or None,
            results_count=results_count,
            error=error,
            warnings=warnings or None,
        )

    @staticmethod
    def get_job(db: Session, job_id: int) -> Job | None:
        """Fetch one job by primary key."""
        return JobManager.get_job(db, job_id)

    @staticmethod
    def list_ai_results(
        db: Session,
        case_id: int,
        *,
        recording_id: int | None = None,
        analysis_type: str | None = None,
    ) -> list[AIResult]:
        """List persisted AI results for a case, optionally filtered.

        Args:
            db: Database session.
            case_id: Primary key of the case.
            recording_id: Restrict to one recording, if given.
            analysis_type: Restrict to one `AnalysisType` value, if given.

        Returns:
            Matching `AIResult` rows, ordered by primary key.
        """
        query = db.query(AIResult).filter(AIResult.case_id == case_id)
        if recording_id is not None:
            query = query.filter(AIResult.recording_id == recording_id)
        if analysis_type is not None:
            query = query.filter(AIResult.analysis_type == analysis_type)
        return query.order_by(AIResult.id).all()

    @staticmethod
    def _process_recording(
        db: Session,
        *,
        job: Job,
        case_id: int,
        recording_id: int,
        requested_types: list[AnalysisType],
        object_model: ModelLoadResult | None,
        face_model: ModelLoadResult | None,
        device: str,
        sampling_strategy: str,
        sampling_value: float | None,
        confidence_threshold: float,
        face_confidence_threshold: float,
        classes: list[str] | None,
        tracker: str,
        frame_redundancy_enabled: bool = False,
        frame_redundancy_threshold: float = DEFAULT_FRAME_REDUNDANCY_THRESHOLD,
        frame_redundancy_max_skip_run: int | None = None,
    ) -> tuple[list[str], int, FrameRedundancyStats | None]:
        """Process one recording. Returns `(warnings, results_created,
        frame_redundancy_stats)` -- the third element is `None` unless
        frame-redundancy optimization actually ran for this recording.

        Never raises for an ordinary per-recording problem (missing
        recording, missing artifact, decoder failure, empty recording,
        corrupt frame) -- every such case is reported as a warning so the
        rest of the batch, and the rest of this recording's other
        analysis types, can still proceed.
        """
        warnings: list[str] = []
        if not requested_types:
            return warnings, 0, None

        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if recording is None:
            return [f"recording {recording_id}: not found"], 0, None

        artifact = AIManager._resolve_source_artifact(db, recording)
        if artifact is None:
            return [f"recording {recording_id}: no derived artifact available"], 0, None

        artifact_path = Path(artifact.path)
        if not artifact_path.is_file():
            return [f"recording {recording_id}: source artifact file missing on disk"], 0, None

        capture = cv2.VideoCapture(str(artifact_path))
        try:
            if not capture.isOpened():
                return (
                    [f"recording {recording_id}: failed to open video (decoder failure)"],
                    0,
                    None,
                )

            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            source_fps = float(capture.get(cv2.CAP_PROP_FPS))
            if frame_count <= 0 or source_fps <= 0:
                return [f"recording {recording_id}: empty or invalid recording"], 0, None

            try:
                strategy = SamplingStrategy(sampling_strategy)
                selections = select_frames(
                    frame_count=frame_count,
                    source_fps=source_fps,
                    strategy=strategy,
                    value=sampling_value,
                )
            except ValueError as exc:
                return [f"recording {recording_id}: {exc}"], 0, None

            samples: list[tuple[int, float, Any]] = []
            for selection in selections:
                capture.set(cv2.CAP_PROP_POS_FRAMES, selection.frame_number)
                ok, frame = capture.read()
                if not ok or frame is None:
                    warnings.append(
                        f"recording {recording_id}: corrupt/unreadable frame "
                        f"{selection.frame_number}"
                    )
                    continue
                samples.append((selection.frame_number, selection.timestamp_seconds, frame))
        finally:
            capture.release()

        if not samples:
            warnings.append(f"recording {recording_id}: no frames could be decoded")
            return warnings, 0, None

        results_created = 0

        camera_id = AIManager._camera_id_for(recording)
        base_timestamp = recording.start_normalized

        run_plain_detection = AnalysisType.OBJECT_DETECTION in requested_types
        if AnalysisType.OBJECT_TRACKING in requested_types and object_model is not None:
            # Tracking's per-frame results already are object detections
            # (now additionally track-linked) -- running a separate plain
            # object-detection pass over the same recording would only
            # duplicate inference and rows.
            run_plain_detection = False
            tracks = run_tracking(
                object_model.model,
                samples,
                tracker=tracker,
                confidence_threshold=confidence_threshold,
                device=device,
                classes=classes,
            )
            created = AIManager._persist_tracks(
                db,
                job=job,
                case_id=case_id,
                recording=recording,
                camera_id=camera_id,
                artifact=artifact,
                tracks=tracks,
                model_version=object_model.model_version,
                tracker=tracker,
                base_timestamp=base_timestamp,
            )
            results_created += created

        # Frame-redundancy optimization (Phase 21, Part B) applies ONLY
        # to the two plain per-frame model-inference loops below --
        # never to tracking (already handled above) or motion detection
        # (below), both of which need every one of their own sampled
        # frames for correct internal continuity/differencing. Tracking
        # and plain object detection are already mutually exclusive
        # (`run_plain_detection` above), so this can never conflict with
        # tracking. Computed at most once per recording and reused for
        # both loops -- the frame content being compared is identical
        # regardless of which detector will run on it.
        will_run_face_detection = (
            AnalysisType.FACE_DETECTION in requested_types and face_model is not None
        )
        redundancy_decisions: list[Any] | None = None
        redundancy_stats: FrameRedundancyStats | None = None
        if frame_redundancy_enabled and (
            (run_plain_detection and object_model is not None) or will_run_face_detection
        ):
            redundancy_config = FrameRedundancyConfig(
                threshold=frame_redundancy_threshold,
                max_skip_run=frame_redundancy_max_skip_run,
                max_timestamp_gap_seconds=AIManager._derive_max_timestamp_gap_seconds(selections),
            )
            comparison_started = time.perf_counter()
            redundancy_decisions = evaluate_redundancy_sequence(samples, redundancy_config)
            comparison_elapsed = time.perf_counter() - comparison_started
            redundancy_stats = summarize_frame_redundancy(
                redundancy_decisions,
                threshold=frame_redundancy_threshold,
                comparison_time_seconds=comparison_elapsed,
            )

        analyze_by_frame_number: dict[int, bool] = (
            {d.frame_number: d.analyze for d in redundancy_decisions}
            if redundancy_decisions is not None
            else {}
        )

        if run_plain_detection and object_model is not None:
            for frame_number, timestamp_seconds, frame in samples:
                if not analyze_by_frame_number.get(frame_number, True):
                    continue
                detections = detect_objects(
                    object_model.model,
                    frame,
                    frame_number=frame_number,
                    timestamp_seconds=timestamp_seconds,
                    confidence_threshold=confidence_threshold,
                    device=device,
                    classes=classes,
                )
                results_created += AIManager._persist_detections(
                    db,
                    job=job,
                    case_id=case_id,
                    recording=recording,
                    artifact=artifact,
                    analysis_type=AnalysisType.OBJECT_DETECTION,
                    model_name=object_model.model_name,
                    model_version=object_model.model_version,
                    detections=detections,
                    base_timestamp=base_timestamp,
                )

        if will_run_face_detection and face_model is not None:
            for frame_number, timestamp_seconds, frame in samples:
                if not analyze_by_frame_number.get(frame_number, True):
                    continue
                detections = detect_faces(
                    face_model.model,
                    frame,
                    frame_number=frame_number,
                    timestamp_seconds=timestamp_seconds,
                    confidence_threshold=face_confidence_threshold,
                )
                results_created += AIManager._persist_detections(
                    db,
                    job=job,
                    case_id=case_id,
                    recording=recording,
                    artifact=artifact,
                    analysis_type=AnalysisType.FACE_DETECTION,
                    model_name=face_model.model_name,
                    model_version=face_model.model_version,
                    detections=detections,
                    base_timestamp=base_timestamp,
                )

        if AnalysisType.MOTION_DETECTION in requested_types:
            motion_events = detect_motion_events(
                samples, threshold=DEFAULT_THRESHOLD, min_area=DEFAULT_MIN_AREA
            )
            results_created += AIManager._persist_motion_events(
                db,
                job=job,
                case_id=case_id,
                recording=recording,
                camera_id=camera_id,
                artifact=artifact,
                events=motion_events,
                base_timestamp=base_timestamp,
            )

        return warnings, results_created, redundancy_stats

    @staticmethod
    def _resolve_source_artifact(db: Session, recording: Recording) -> Artifact | None:
        """Resolve the derived MP4 artifact to decode frames from.

        Prefers the Phase 9 H.264 preview artifact (most reliable OpenCV
        decode compatibility); falls back to the H.265 master artifact.
        Never reopens the original proprietary evidence format.
        """
        preview_row = (
            db.query(RecordingMetadata)
            .filter(
                RecordingMetadata.recording_id == recording.id,
                RecordingMetadata.key == _PREVIEW_ARTIFACT_METADATA_KEY,
            )
            .first()
        )
        artifact_id: int | None = None
        if preview_row is not None and preview_row.value is not None:
            artifact_id = int(preview_row.value)
        elif recording.artifact_id is not None:
            artifact_id = int(recording.artifact_id)

        if artifact_id is None:
            return None
        return db.query(Artifact).filter(Artifact.id == artifact_id).first()

    @staticmethod
    def _derive_max_timestamp_gap_seconds(selections: Sequence[Any]) -> float | None:
        """Derive `FrameRedundancyConfig.max_timestamp_gap_seconds` from
        this job's own actual sampling interval, rather than hardcoding
        one fixed number of seconds for every job regardless of its
        sampling rate.

        Uses the median gap between consecutive selected timestamps (the
        job's typical interval), scaled by
        `_TIMESTAMP_DISCONTINUITY_INTERVAL_MULTIPLIER` -- a gap that many
        times larger than normal is treated as a possible seek/
        discontinuity in the source rather than an ordinary consecutive
        sampled frame.

        Returns `None` (disabling the check) when fewer than two
        selections exist or the derived interval is non-positive.
        """
        if len(selections) < 2:
            return None
        gaps = [
            b.timestamp_seconds - a.timestamp_seconds
            for a, b in zip(selections, selections[1:], strict=False)
        ]
        positive_gaps = [gap for gap in gaps if gap > 0]
        if not positive_gaps:
            return None
        typical_interval = float(statistics.median(positive_gaps))
        if typical_interval <= 0:
            return None
        return typical_interval * _TIMESTAMP_DISCONTINUITY_INTERVAL_MULTIPLIER

    @staticmethod
    def _camera_id_for(recording: Recording) -> str | None:
        """Same camera-identity fallback Phase 12's `TimelineManager` uses."""
        if recording.camera_id is not None:
            return recording.camera_id
        if recording.channel is not None:
            return str(recording.channel)
        return None

    @staticmethod
    def _absolute_timestamp(
        base_timestamp: datetime | None, offset_seconds: float
    ) -> datetime | None:
        """Compute an absolute normalized timestamp, or `None` if unavailable.

        Never fabricated: only computed when the recording actually has a
        normalized start (Phase 11 output).
        """
        if base_timestamp is None:
            return None
        return base_timestamp + timedelta(seconds=offset_seconds)

    @staticmethod
    def _persist_detections(
        db: Session,
        *,
        job: Job,
        case_id: int,
        recording: Recording,
        artifact: Artifact,
        analysis_type: AnalysisType,
        model_name: str,
        model_version: str,
        detections: list[Detection],
        base_timestamp: datetime | None,
        track_row_id: int | None = None,
    ) -> int:
        created = 0
        for detection in detections:
            row = AIResult(
                job_id=job.id,
                case_id=case_id,
                recording_id=recording.id,
                analysis_type=analysis_type.value,
                model_name=model_name,
                model_version=model_version,
                frame_number=detection.frame_number,
                timestamp=AIManager._absolute_timestamp(
                    base_timestamp, detection.timestamp_seconds
                ),
                class_name=detection.class_name,
                confidence=detection.confidence,
                bbox_x_min=detection.bbox.x_min,
                bbox_y_min=detection.bbox.y_min,
                bbox_x_max=detection.bbox.x_max,
                bbox_y_max=detection.bbox.y_max,
                track_id=track_row_id,
                source_artifact=artifact.id,
            )
            db.add(row)
            created += 1
        if created:
            db.commit()
        return created

    @staticmethod
    def _persist_tracks(
        db: Session,
        *,
        job: Job,
        case_id: int,
        recording: Recording,
        camera_id: str | None,
        artifact: Artifact,
        tracks: list[Track],
        model_version: str,
        tracker: str,
        base_timestamp: datetime | None,
    ) -> int:
        created = 0
        for track in tracks:
            trajectory_payload = [
                {
                    "frame_number": point.frame_number,
                    "timestamp_seconds": point.timestamp_seconds,
                    "bbox": {
                        "x_min": point.bbox.x_min,
                        "y_min": point.bbox.y_min,
                        "x_max": point.bbox.x_max,
                        "y_max": point.bbox.y_max,
                    },
                    "confidence": point.confidence,
                }
                for point in track.trajectory
            ]
            track_row = AITrack(
                job_id=job.id,
                case_id=case_id,
                recording_id=recording.id,
                camera_id=camera_id,
                track_id=track.track_id,
                class_name=track.class_name,
                first_seen=AIManager._absolute_timestamp(
                    base_timestamp, track.first_seen_timestamp_seconds
                ),
                last_seen=AIManager._absolute_timestamp(
                    base_timestamp, track.last_seen_timestamp_seconds
                ),
                first_seen_frame=track.first_seen_frame,
                last_seen_frame=track.last_seen_frame,
                trajectory=json.dumps(trajectory_payload),
                frame_count=track.frame_count,
                average_confidence=track.average_confidence,
                model_version=model_version,
                tracker_version=f"{tracker} (ultralytics)",
                source_artifact=artifact.id,
            )
            db.add(track_row)
            db.commit()
            db.refresh(track_row)
            created += 1

            point_detections = [
                Detection(
                    class_name=track.class_name,
                    confidence=point.confidence,
                    bbox=point.bbox,
                    frame_number=point.frame_number,
                    timestamp_seconds=point.timestamp_seconds,
                    track_id=track_row.id,
                )
                for point in track.trajectory
            ]
            created += AIManager._persist_detections(
                db,
                job=job,
                case_id=case_id,
                recording=recording,
                artifact=artifact,
                analysis_type=AnalysisType.OBJECT_TRACKING,
                model_name="yolov8n",
                model_version=model_version,
                detections=point_detections,
                base_timestamp=base_timestamp,
                track_row_id=track_row.id,
            )
        return created

    @staticmethod
    def _persist_motion_events(
        db: Session,
        *,
        job: Job,
        case_id: int,
        recording: Recording,
        camera_id: str | None,
        artifact: Artifact,
        events: list[MotionEventResult],
        base_timestamp: datetime | None,
    ) -> int:
        created = 0
        for event in events:
            regions_payload = [
                {
                    "frame_number": region.frame_number,
                    "timestamp_seconds": region.timestamp_seconds,
                    "bbox": {
                        "x_min": region.bbox.x_min,
                        "y_min": region.bbox.y_min,
                        "x_max": region.bbox.x_max,
                        "y_max": region.bbox.y_max,
                    },
                }
                for region in event.regions
            ]
            row = MotionEvent(
                job_id=job.id,
                case_id=case_id,
                recording_id=recording.id,
                camera_id=camera_id,
                start_time=AIManager._absolute_timestamp(base_timestamp, event.start_time_seconds),
                end_time=AIManager._absolute_timestamp(base_timestamp, event.end_time_seconds),
                regions=json.dumps(regions_payload),
                score=event.score,
                method=MOTION_METHOD_NAME,
                parameters=json.dumps(
                    {"threshold": DEFAULT_THRESHOLD, "min_area": DEFAULT_MIN_AREA}
                ),
                source_artifact=artifact.id,
            )
            db.add(row)
            created += 1
        if created:
            db.commit()
        return created
