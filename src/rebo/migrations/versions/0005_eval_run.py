"""Eval runs recorded in the state store, for accuracy over time in Insights.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "eval_run" not in set(sa.inspect(op.get_bind()).get_table_names()):
        op.create_table(
            "eval_run",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("at", sa.Float(), nullable=False),
            sa.Column("kind", sa.Text(), nullable=False),       # questions | conversations
            sa.Column("cases", sa.Text(), nullable=False),      # the cases file
            sa.Column("model", sa.Text()),
            sa.Column("summary", sa.Text(), nullable=False),    # JSON summary as in the results file
            sa.Column("results_file", sa.Text()),
        )


def downgrade() -> None:
    raise NotImplementedError("the state store only moves forward; restore a backup instead")
