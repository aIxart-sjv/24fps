"""
SQLAlchemy ORM models for AI analysis output (Phase 13).
Master Specification Section 30-34 ("AI Backend", "Object Detection",
"Object Tracking", "Face Detection", "Motion Detection"), Section 50
(`ai_results` table), Section 51 rule 7 ("AI results must reference the
source artifact/recording").

Three tables, not one:
- `AIResult` matches Section 50's own `ai_results` table almost exactly
  (it already lists this table) -- one row per single-frame object/face
  detection.
- `AITrack` and `MotionEvent` are new beyond Section 50's terse list, but
  each is directly justified by the master spec's own fuller conceptual
  model: Section 32's "Tracking result" (track_id, recording_id,
  camera_id, class, first_seen, last_seen, trajectory, frame_count,
  average_confidence, model_version, tracker_version) and Section 34's
  "Motion event" (motion_event_id, recording_id, camera_id, start_time,
  end_time, regions, confidence/score, method, parameters,
  source_artifact) are both distinct, richer concepts that do not fit
  `ai_results`' one-row-per-frame-detection shape (a track aggregates many
  frames; a motion event spans a time range with possibly several
  regions). This is the exact resolution pattern Phase 10 (`evidence_id`
  on `recovery_results`) and Phase 12 (`timeline_events` itself, beyond
  Section 50's terser column list) already established for a terse-DB-
  list-vs-richer-conceptual-model gap.

`job_id`/`case_id`/`source_artifact` are added to all three tables beyond
either section's own list, directly required by Section 35 ("Every AI job
must be reproducible from: source artifact...output records") and Section
51 rule 7 -- `source_artifact` is NOT NULL everywhere: "Never store an AI
result without a source artifact/frame reference" is enforced at the
database level, not just by convention.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.artifact import Artifact
    from app.models.case import Case
    from app.models.job import Job
    from app.models.recording import Recording


class AIResult(Base):
    """One object/face detection on one sampled frame.

    `analysis_type` is `"object_detection"` or `"face_detection"`
    (`app.ai.types.AnalysisType`) -- motion events and aggregate tracks
    live in `MotionEvent`/`AITrack`, not here. `bbox_x_min/y_min/x_max/
    y_max` are 4 real float columns (not a JSON blob): both the Master
    Specification and the NTRO requirements explicitly name exactly these
    4 fields as the project's bounding-box representation, and a
    fixed-cardinality tuple is better served by typed columns than an
    opaque string.

    `class_name` is a plain label ("person", "car", "face") -- never an
    identity (Master Specification Section 33: face detection is not face
    recognition).
    """

    __tablename__ = "ai_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recording_id: Mapped[int] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Absolute, normalized timestamp of this frame (`Recording.
    #: start_normalized` + frame offset) when available; `NULL` when the
    #: recording has no normalized start -- never fabricated. Consumers
    #: needing a frame reference when this is `NULL` fall back to
    #: `frame_number` (task Phase 13 scope: "a timestamp or equivalent
    #: frame reference").
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    class_name: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x_min: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y_min: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x_max: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y_max: Mapped[float] = mapped_column(Float, nullable=False)
    #: References `AITrack.id` (the surrogate PK), not the tracker's raw
    #: local integer -- `AITrack.track_id` carries that for display.
    #: `NULL` when tracking was not run for this detection.
    track_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_tracks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_artifact: Mapped[int] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    job: Mapped[Job | None] = relationship("Job")
    case: Mapped[Case] = relationship("Case", back_populates="ai_results")
    recording: Mapped[Recording] = relationship("Recording")
    artifact: Mapped[Artifact] = relationship("Artifact")
    track: Mapped[AITrack | None] = relationship("AITrack", back_populates="detections")

    def __repr__(self) -> str:
        return f"<AIResult analysis_type={self.analysis_type!r} class_name={self.class_name!r}>"


class AITrack(Base):
    """One aggregated object track across multiple sampled frames
    (Master Specification Section 32).

    `track_id` is the tracker-assigned integer (ByteTrack/BoT-SORT's own
    local ID), unique only within `(job_id, recording_id)` -- `id` is the
    real, globally-unique surrogate primary key other tables reference.

    Never a claim of identity (Section 32: "Tracking does not
    automatically prove identity.") -- no field on this model names a
    person, only a track reference and a class label.
    """

    __tablename__ = "ai_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recording_id: Mapped[int] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    #: JSON-encoded list of `{frame_number, timestamp_seconds, bbox,
    #: confidence}` points -- variable-length, so JSON-in-text rather than
    #: fixed columns (matching the `RecordingMetadata` precedent).
    trajectory: Mapped[str | None] = mapped_column(Text, nullable=True)
    frame_count: Mapped[int] = mapped_column(Integer, nullable=False)
    average_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    tracker_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_artifact: Mapped[int] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    job: Mapped[Job | None] = relationship("Job")
    case: Mapped[Case] = relationship("Case", back_populates="ai_tracks")
    recording: Mapped[Recording] = relationship("Recording")
    artifact: Mapped[Artifact] = relationship("Artifact")
    detections: Mapped[list[AIResult]] = relationship("AIResult", back_populates="track")

    def __repr__(self) -> str:
        return f"<AITrack track_id={self.track_id!r} class_name={self.class_name!r}>"


class MotionEvent(Base):
    """One contiguous span of detected motion (Master Specification
    Section 34).

    `regions` is a JSON-encoded list of per-sampled-frame changed-pixel
    rectangles (variable cardinality, so JSON-in-text). `method`/
    `parameters` record exactly which classical-CV algorithm and
    threshold produced this event, so the result is reproducible without
    re-running inference to find out.
    """

    __tablename__ = "motion_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recording_id: Mapped[int] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    regions: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_artifact: Mapped[int] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    job: Mapped[Job | None] = relationship("Job")
    case: Mapped[Case] = relationship("Case", back_populates="motion_events")
    recording: Mapped[Recording] = relationship("Recording")
    artifact: Mapped[Artifact] = relationship("Artifact")

    def __repr__(self) -> str:
        return f"<MotionEvent recording_id={self.recording_id!r} method={self.method!r}>"
