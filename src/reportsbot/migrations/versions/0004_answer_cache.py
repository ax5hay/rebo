"""Exact answer cache (B-031).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "answer_cache" not in set(sa.inspect(op.get_bind()).get_table_names()):
        op.create_table(
            "answer_cache",
            sa.Column("key", sa.Text(), primary_key=True),   # hash of question, user scope, knowledge + catalog version
            sa.Column("owner", sa.Text(), nullable=False),
            sa.Column("sql", sa.Text(), nullable=False),
            sa.Column("report", sa.Text(), nullable=False),  # JSON: title, assumptions, follow_ups, used_knowledge
            sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.Float(), nullable=False),
        )


def downgrade() -> None:
    raise NotImplementedError("the state store only moves forward; restore a backup instead")
