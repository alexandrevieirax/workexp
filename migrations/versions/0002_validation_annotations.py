"""validation_sample: item id, comment and timestamp for human annotations

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("validation_sample") as batch:
        batch.add_column(sa.Column("item_id", sa.String(length=64), nullable=True,
                                   comment="Benchmark item id (e.g. tc-001)"))
        batch.add_column(sa.Column("comment", sa.Text(), nullable=True, comment="Annotator's free-text note"))
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_validation_sample_item", ["sample_set", "item_id", "right_ref", "annotator"])


def downgrade() -> None:
    with op.batch_alter_table("validation_sample") as batch:
        batch.drop_index("ix_validation_sample_item")
        batch.drop_column("created_at")
        batch.drop_column("comment")
        batch.drop_column("item_id")
