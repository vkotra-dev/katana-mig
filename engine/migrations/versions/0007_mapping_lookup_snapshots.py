"""mapping and lookup snapshot tables

Revision ID: 0007_mapping_lookup_snapshots
Revises: 0006_user_session_version
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_mapping_lookup_snapshots"
down_revision = "0006_user_session_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mapping_snapshots",
        sa.Column("mapping_snapshot_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project_registry.project_id"), nullable=False),
        sa.Column("destination_object_name", sa.String(length=255), nullable=False),
        sa.Column("mapping_snapshot_version", sa.String(length=64), nullable=False),
        sa.Column("field_bindings", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(length=36), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_mapping_snapshots_project_dest_version",
        "mapping_snapshots",
        ["project_id", "destination_object_name", "mapping_snapshot_version"],
        unique=True,
    )

    op.create_table(
        "lookup_snapshots",
        sa.Column("lookup_snapshot_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project_registry.project_id"), nullable=False),
        sa.Column("lookup_name", sa.String(length=128), nullable=False),
        sa.Column("lookup_snapshot_version", sa.String(length=64), nullable=False),
        sa.Column("value_map", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(length=36), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_lookup_snapshots_project_name_version",
        "lookup_snapshots",
        ["project_id", "lookup_name", "lookup_snapshot_version"],
        unique=True,
    )

    op.create_table(
        "mapping_artifacts",
        sa.Column("mapping_artifact_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("run_records.run_id"), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project_registry.project_id"), nullable=False),
        sa.Column("destination_object_name", sa.String(length=255), nullable=False),
        sa.Column("mapping_snapshot_version", sa.String(length=64), nullable=False),
        sa.Column("lookup_snapshot_version", sa.String(length=64), nullable=False),
        sa.Column("mapped_rows", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mapping_artifacts")
    op.drop_index("ix_lookup_snapshots_project_name_version", table_name="lookup_snapshots")
    op.drop_table("lookup_snapshots")
    op.drop_index("ix_mapping_snapshots_project_dest_version", table_name="mapping_snapshots")
    op.drop_table("mapping_snapshots")
