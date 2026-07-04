"""add source_definition_id and destination_fields to mapping_snapshots

Revision ID: 0023_mapping_snapshot_source_id
Revises: 0022_project_resources
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0023_mapping_snapshot_source_id"
down_revision = "0022_project_resources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mapping_snapshots") as batch_op:
        batch_op.add_column(sa.Column("source_definition_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("destination_fields", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            "fk_mapping_snapshots_source_def",
            "source_definitions",
            ["source_definition_id"],
            ["source_definition_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("mapping_snapshots") as batch_op:
        batch_op.drop_constraint("fk_mapping_snapshots_source_def", type_="foreignkey")
        batch_op.drop_column("destination_fields")
        batch_op.drop_column("source_definition_id")
