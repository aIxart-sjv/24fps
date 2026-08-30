"""phase_12_timeline_events

Revision ID: a1c4e8f26b73
Revises: f3a7c1e9b2d4
Create Date: 2026-08-30 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c4e8f26b73"
down_revision: str | None = "f3a7c1e9b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("recording_id", sa.Integer(), nullable=True),
        sa.Column("camera_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("original_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("normalized_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ai_reference", sa.String(length=128), nullable=True),
        sa.Column("recovery_status", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["correlation_id"], ["timeline_events.id"]),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_timeline_events_camera_id"), "timeline_events", ["camera_id"], unique=False
    )
    op.create_index(
        op.f("ix_timeline_events_case_id"), "timeline_events", ["case_id"], unique=False
    )
    op.create_index(
        op.f("ix_timeline_events_correlation_id"),
        "timeline_events",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_timeline_events_event_type"), "timeline_events", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_timeline_events_recording_id"),
        "timeline_events",
        ["recording_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_timeline_events_recording_id"), table_name="timeline_events")
    op.drop_index(op.f("ix_timeline_events_event_type"), table_name="timeline_events")
    op.drop_index(op.f("ix_timeline_events_correlation_id"), table_name="timeline_events")
    op.drop_index(op.f("ix_timeline_events_case_id"), table_name="timeline_events")
    op.drop_index(op.f("ix_timeline_events_camera_id"), table_name="timeline_events")
    op.drop_table("timeline_events")
