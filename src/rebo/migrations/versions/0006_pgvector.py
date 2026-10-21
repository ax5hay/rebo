"""pgvector on Postgres: vectors searched in the database (B-026 follow-up).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-21

On Postgres with the `vector` extension available (image pgvector/pgvector:0.8.7-pg18), the embedding
table gains `vec vector` and dense search runs in SQL. Without the extension, or on SQLite, nothing
changes: vectors stay in the BYTEA/BLOB column and are searched in-process.
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    available = bind.exec_driver_sql("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'").first()
    if not available:
        return
    bind.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    if "vec" not in {c["name"] for c in sa.inspect(bind).get_columns("embedding")}:
        bind.exec_driver_sql("ALTER TABLE embedding ADD COLUMN vec vector")


def downgrade() -> None:
    raise NotImplementedError("the state store only moves forward; restore a backup instead")
