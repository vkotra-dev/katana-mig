"""fix mapping_snapshots unique constraint to include source_definition_id

Revision ID: 0024_mapping_per_feed
Revises: 0023_mapping_snapshot_source_id
Create Date: 2026-07-05
"""
from __future__ import annotations

from alembic import op

revision = "0024_mapping_per_feed"
down_revision = "0023_mapping_snapshot_source_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the new feed-scoped index before dropping the old project-scoped one
    # so MySQL retains a covering index for FK constraints during the transition.
    op.create_index(
        "ix_mapping_snapshots_source_dest_version",
        "mapping_snapshots",
        ["project_id", "source_definition_id", "destination_object_name", "mapping_snapshot_version"],
        unique=True,
    )
    op.drop_index("ix_mapping_snapshots_project_dest_version", table_name="mapping_snapshots")


def downgrade() -> None:
    op.create_index(
        "ix_mapping_snapshots_project_dest_version",
        "mapping_snapshots",
        ["project_id", "destination_object_name", "mapping_snapshot_version"],
        unique=True,
    )
    op.drop_index("ix_mapping_snapshots_source_dest_version", table_name="mapping_snapshots")
