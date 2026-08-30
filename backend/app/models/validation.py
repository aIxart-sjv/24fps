"""
SQLAlchemy ORM models for the validation/ground-truth layer (Phase 14).
Master Specification Section 36 ("Validation Engine"), Section 37
("Ground-Truth Dataset Model"), Section 50 (`validation_runs` table),
Section 51 rule 9 ("Validation must reference the ground truth").

Two tables, not one per validation type (task Phase 14 scope: "Do not
create separate ground-truth models for every AI type unless necessary"):

- `GroundTruth` generalizes Section 37's recovery-only test-case model
  (ground_truth_id, device_id, recording_id, scenario, expected_start/
  end/duration/frames/fragments/hash, notes) to also cover the task's
  own broader field list spanning object/face/motion/track/correlation
  events (event_type, timestamp/frame, object class, bbox, expected
  track/group relationship) -- the identical terse-conceptual-model-vs-
  broader-task-scope gap Phase 10/12/13 already resolved for
  `recovery_results`/`timeline_events`/`ai_results`, resolved the same
  way here: one flexible table.
- `ValidationMetric` is the flat, per-named-metric shape Section 18 of
  the task itself describes ("metric name, metric value, numerator/
  denominator") -- a validation run produces a *list* of named metrics
  (precision, recall, F1, TP/FP/FN, timing error, ...), which does not
  fit as fixed columns on one row the way Section 50's recovery-specific
  `validation_runs` table (recovery_rate, timestamp_accuracy, ...) does.

Deliberately NOT created: a third "ValidationRun" table. `app.models.job.
Job` (Phase 13) already is the generic run/job envelope Section 50's
`validation_runs` table needs (id, case_id, job_type, status, progress,
created_at/started_at/completed_at, parameters, software_version,
results_count, error, warnings) -- `ValidationManager` writes
`job_type="validation"` rows there, with `validation_type`/`dataset_id`
inside `Job.parameters`, exactly matching the task's own instruction:
"Do NOT create a second metrics system if an existing metrics/
observability structure is sufficient."
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.job import Job
    from app.models.recording import Recording

__all__ = ["GroundTruth", "ValidationMetric"]


class GroundTruth(Base):
    """One independently-known expected fact about a controlled scenario.

    `dataset_id` groups multiple rows into one controlled experiment
    (e.g. every expected event in one A -> B -> C camera-sequence
    scenario, or one deleted-recording recovery experiment).
    `group_reference` further groups rows *within* a dataset into one
    expected track or one expected event sequence (the "expected track/
    group relationship" the task's own field list names).

    Ground truth is always independently supplied (a controlled test
    scenario, an examiner annotation) -- nothing in this codebase reads
    an `AIResult`/`MotionEvent`/`AITrack`/`TimelineEvent` row and writes
    a `GroundTruth` row from it (task Phase 14 scope section 4: "Ground
    truth must not simply copy AI output").
    """

    __tablename__ = "ground_truth"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recording_id: Mapped[int | None] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    camera_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    #: One of `app.validation.benchmark.ValidationType`'s values -- the
    #: same vocabulary `ValidationMetric.validation_type` uses, so
    #: `ValidationManager.run_validation` can look up a dataset's ground
    #: truth by `validation_type` directly, with no separate mapping.
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    object_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frame_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_x_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_x_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Master Specification Section 37's recovery test-case fields, verbatim.
    expected_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_fragments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    group_reference: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    case: Mapped[Case] = relationship("Case", back_populates="ground_truth_records")
    recording: Mapped[Recording | None] = relationship("Recording")

    def __repr__(self) -> str:
        return f"<GroundTruth dataset_id={self.dataset_id!r} event_type={self.event_type!r}>"


class ValidationMetric(Base):
    """One named metric produced by one validation run.

    `job_id` links back to the `Job` row (`job_type="validation"`) that
    produced this metric -- full reproducibility (which run, which
    parameters, which software/model versions) without duplicating that
    metadata onto every metric row. `dataset_id`/`validation_type` are
    denormalized here for direct querying, mirroring how `AIResult`
    denormalizes `case_id`/`recording_id` even though both are derivable
    via `job_id`.
    """

    __tablename__ = "validation_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validation_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    numerator: Mapped[float | None] = mapped_column(Float, nullable=True)
    denominator: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    job: Mapped[Job] = relationship("Job")
    case: Mapped[Case] = relationship("Case", back_populates="validation_metrics")

    def __repr__(self) -> str:
        return f"<ValidationMetric metric_name={self.metric_name!r} value={self.metric_value!r}>"
