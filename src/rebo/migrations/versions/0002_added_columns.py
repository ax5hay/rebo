"""Columns added after the first release (formerly store.MIGRATIONS); each only if missing.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUMNS = [
    ("knowledge_event", sa.Column("turn_id", sa.Text())),
    ("turn", sa.Column("feedback_note", sa.Text())),
    ("knowledge", sa.Column("sql_template", sa.Text())),       # example: literals -> :pN
    ("knowledge", sa.Column("params", sa.Text())),             # JSON list of the literals
    ("knowledge", sa.Column("pinned", sa.Integer(), nullable=False, server_default="0")),  # owner's favourite
    ("cat_column", sa.Column("pos", sa.Integer())),            # column order (was SQLite's rowid)
]


def upgrade() -> None:
    bind = op.get_bind()
    for table, column in COLUMNS:
        if column.name not in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table, column)
            if (table, column.name) == ("cat_column", "pos") and bind.dialect.name == "sqlite":
                op.execute("UPDATE cat_column SET pos=rowid")  # keep the order of an existing catalog


def downgrade() -> None:
    raise NotImplementedError("the state store only moves forward; restore a backup instead")
