"""phase_10_recovery_results

Revision ID: f3a7c1e9b2d4
Revises: 8b1f2c9d4a6e
Create Date: 2026-08-29 20:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a7c1e9b2d4"
down_revision: str | None = "8b1f2c9d4a6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recovery_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("fragments_found", sa.Integer(), nullable=True),
        sa.Column("fragments_used", sa.Integer(), nullable=True),
        sa.Column("fragments_missing", sa.Integer(), nullable=True),
        sa.Column("frames_expected", sa.Integer(), nullable=True),
        sa.Column("frames_recovered", sa.Integer(), nullable=True),
        sa.Column("recovery_rate", sa.Float(), nullable=True),
        sa.Column("timestamp_error", sa.Float(), nullable=True),
        sa.Column("frame_continuity", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_offset", sa.BigInteger(), nullable=True),
        sa.Column("source_length", sa.BigInteger(), nullable=True),
        sa.Column("recovery_engine_version", sa.String(length=32), nullable=True),
        sa.Column("parser_version", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_recovery_results_artifact_id"), "recovery_results", ["artifact_id"], unique=False
    )
    op.create_index(
        op.f("ix_recovery_results_evidence_id"), "recovery_results", ["evidence_id"], unique=False
    )
    op.create_index(
        op.f("ix_recovery_results_recording_id"), "recovery_results", ["recording_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_recovery_results_recording_id"), table_name="recovery_results")
    op.drop_index(op.f("ix_recovery_results_evidence_id"), table_name="recovery_results")
    op.drop_index(op.f("ix_recovery_results_artifact_id"), table_name="recovery_results")
    op.drop_table("recovery_results")
