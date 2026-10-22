"""Embedding text hashes: a re-bootstrap embeds only schema text that changed.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22

`embedding.text_hash` holds a hash of the text a vector was computed from. Bootstrap compares it and
skips unchanged documents (on Orbitra, embedding was 10.7 of 13.9 s). Rows from before have no hash
and are embedded once more, then kept.
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "text_hash" not in {c["name"] for c in sa.inspect(bind).get_columns("embedding")}:
        op.add_column("embedding", sa.Column("text_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    raise NotImplementedError("the state store only moves forward; restore a backup instead")
