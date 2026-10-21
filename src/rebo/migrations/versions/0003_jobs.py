"""Durable jobs and report schedules (B-030).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "job" not in existing:
        op.create_table(
            "job",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("kind", sa.Text(), nullable=False),          # ask | scheduled
            sa.Column("owner", sa.Text(), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),       # JSON: what to run and where to deliver it
            sa.Column("status", sa.Text(), nullable=False),        # queued | running | done | failed
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("run_after", sa.Float(), nullable=False),
            sa.Column("lease_until", sa.Float()),                  # a running job whose lease passed is retried
            sa.Column("result", sa.Text()),                        # JSON of the turn it produced
            sa.Column("error", sa.Text()),
            sa.Column("created_at", sa.Float(), nullable=False),
            sa.Column("updated_at", sa.Float(), nullable=False),
        )
        op.create_index("job_due", "job", ["status", "run_after"])
    if "schedule" not in existing:
        op.create_table(
            "schedule",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("owner", sa.Text(), nullable=False),
            sa.Column("turn_id", sa.Text(), nullable=False),       # the report to re-run (no model)
            sa.Column("every", sa.Text(), nullable=False),         # "monday 08:00", "daily 07:30", "weekdays 09:00"
            sa.Column("deliver", sa.Text()),                       # JSON: e.g. {"kind": "jms", "contact_id": 7}
            sa.Column("next_at", sa.Float(), nullable=False),
            sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.Float(), nullable=False),
        )


def downgrade() -> None:
    raise NotImplementedError("the state store only moves forward; restore a backup instead")
