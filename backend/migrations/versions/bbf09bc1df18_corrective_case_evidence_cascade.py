"""corrective_case_evidence_cascade

Revision ID: bbf09bc1df18
Revises: 2f5e9d71fc70
Create Date: 2026-08-26 23:17:47.670349

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbf09bc1df18'
down_revision: str | None = '2f5e9d71fc70'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The original constraint was created unnamed; this naming convention lets
# batch mode assign it a deterministic name during reflection so it can be
# matched and dropped.
_NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def upgrade() -> None:
    # Remove ondelete=CASCADE on evidence.case_id so deleting a Case can
    # never silently cascade-delete forensic Evidence rows.
    with op.batch_alter_table(
        "evidence", schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint("fk_evidence_case_id_cases", type_="foreignkey")
        batch_op.create_foreign_key("fk_evidence_case_id_cases", "cases", ["case_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table(
        "evidence", schema=None, naming_convention=_NAMING_CONVENTION
    ) as batch_op:
        batch_op.drop_constraint("fk_evidence_case_id_cases", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_evidence_case_id_cases",
            "cases",
            ["case_id"],
            ["id"],
            ondelete="CASCADE",
        )