"""phase_9_recording_metadata

Revision ID: 8b1f2c9d4a6e
Revises: 554c260c0889
Create Date: 2026-08-29 19:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b1f2c9d4a6e'
down_revision: str | None = '554c260c0889'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('metadata',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recording_id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('value', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=128), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['recording_id'], ['recordings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_metadata_recording_id'), 'metadata', ['recording_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_metadata_recording_id'), table_name='metadata')
    op.drop_table('metadata')
