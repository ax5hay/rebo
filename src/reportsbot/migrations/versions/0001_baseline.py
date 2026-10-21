"""Baseline: every table of the first release (idempotent, so existing state files adopt Alembic).

Revision ID: 0001
Revises:
Create Date: 2026-10-21
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from reportsbot.store import SCHEMA, _pg_schema
    bind = op.get_bind()
    script = SCHEMA if bind.dialect.name == "sqlite" else _pg_schema()
    for stmt in script.split(";\n"):
        body = "\n".join(line for line in stmt.splitlines() if not line.strip().startswith("--")).strip()
        if body and not body.upper().startswith("PRAGMA"):
            bind.exec_driver_sql(body)


def downgrade() -> None:
    raise NotImplementedError("the state store only moves forward; restore a backup instead")
