"""add fiber and lookup entity tables

Revision ID: 0019_fiber_models
Revises: 0015_reconciliation_tables
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_fiber_models"
down_revision = "0015_reconciliation_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_fibers",
        sa.Column("fiber_id", sa.String(36), primary_key=True),
        sa.Column("feed_id", sa.String(36), sa.ForeignKey("source_definitions.source_definition_id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project_registry.project_id"), nullable=False),
        sa.Column("fiber_type", sa.String(32), nullable=False),
        sa.Column("fiber_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default=sa.text("'created'")),
        sa.Column("source", sa.String(16), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("proposed_mappings", sa.JSON(), nullable=True),
        sa.Column("field_bindings", sa.JSON(), nullable=True),
        sa.Column("output_sql", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_project_fibers_feed_id", "project_fibers", ["feed_id"])
    op.create_index("ix_project_fibers_project_id", "project_fibers", ["project_id"])

    op.create_table(
        "lookup_source_entries",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column("fiber_id", sa.String(36), sa.ForeignKey("project_fibers.fiber_id"), nullable=False),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("source_value", sa.String(512), nullable=False),
        sa.Column("discovery_type", sa.String(16), nullable=False, server_default=sa.text("'sample'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lookup_source_entries_fiber_id", "lookup_source_entries", ["fiber_id"])

    op.create_table(
        "lookup_dest_feeds",
        sa.Column("dest_feed_id", sa.String(36), primary_key=True),
        sa.Column("fiber_id", sa.String(36), sa.ForeignKey("project_fibers.fiber_id"), nullable=False, unique=True),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "lookup_dest_entries",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column("dest_feed_id", sa.String(36), sa.ForeignKey("lookup_dest_feeds.dest_feed_id"), nullable=False),
        sa.Column("row_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lookup_dest_entries_dest_feed_id", "lookup_dest_entries", ["dest_feed_id"])

    op.create_table(
        "lookup_mappings",
        sa.Column("mapping_id", sa.String(36), primary_key=True),
        sa.Column("fiber_id", sa.String(36), sa.ForeignKey("project_fibers.fiber_id"), nullable=False),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("source_entry_id", sa.String(36), sa.ForeignKey("lookup_source_entries.entry_id"), nullable=False),
        sa.Column("source_value", sa.String(512), nullable=False),
        sa.Column("dest_entry_id", sa.String(36), sa.ForeignKey("lookup_dest_entries.entry_id"), nullable=True),
        sa.Column("dest_row", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'proposed'")),
        sa.Column("mapped_by", sa.String(16), nullable=False, server_default=sa.text("'ai'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lookup_mappings_fiber_id", "lookup_mappings", ["fiber_id"])
    op.create_index("ix_lookup_mappings_source_entry_id", "lookup_mappings", ["source_entry_id"])


def downgrade() -> None:
    op.drop_index("ix_lookup_mappings_source_entry_id", table_name="lookup_mappings")
    op.drop_index("ix_lookup_mappings_fiber_id", table_name="lookup_mappings")
    op.drop_table("lookup_mappings")

    op.drop_index("ix_lookup_dest_entries_dest_feed_id", table_name="lookup_dest_entries")
    op.drop_table("lookup_dest_entries")

    op.drop_table("lookup_dest_feeds")

    op.drop_index("ix_lookup_source_entries_fiber_id", table_name="lookup_source_entries")
    op.drop_table("lookup_source_entries")

    op.drop_index("ix_project_fibers_project_id", table_name="project_fibers")
    op.drop_index("ix_project_fibers_feed_id", table_name="project_fibers")
    op.drop_table("project_fibers")
