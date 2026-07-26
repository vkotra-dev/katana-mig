"""add destination_ddl to source_schema_artifact

Revision ID: 0042
Revises: 0041
"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"


def upgrade() -> None:
    op.add_column(
        "source_schema_artifacts",
        sa.Column("destination_ddl", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_schema_artifacts", "destination_ddl")
