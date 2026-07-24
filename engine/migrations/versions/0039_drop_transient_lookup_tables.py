"""drop transient lookup tables

Revision ID: 0039
Revises: 0038
Create Date: 2026-07-24

Removes the 4 deprecated transient lookup tables that were replaced
by ProjectFiber.proposed_mappings JSON storage (Task 001fh).
"""

from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop foreign-key-dependent tables first
    op.drop_table("lookup_mappings")
    op.drop_table("lookup_dest_entries")
    op.drop_table("lookup_dest_feeds")
    op.drop_table("lookup_source_entries")


def downgrade() -> None:
    # Re-create tables in reverse dependency order
    op.create_table(
        "lookup_source_entries",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column("fiber_id", sa.String(36), nullable=False),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("source_value", sa.String(512), nullable=False),
        sa.Column("discovery_type", sa.String(16), nullable=False, server_default="sample"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "lookup_dest_feeds",
        sa.Column("dest_feed_id", sa.String(36), primary_key=True),
        sa.Column("fiber_id", sa.String(36), nullable=False, unique=True),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("columns", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "lookup_dest_entries",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column("dest_feed_id", sa.String(36), nullable=False),
        sa.Column("row_data", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "lookup_mappings",
        sa.Column("mapping_id", sa.String(36), primary_key=True),
        sa.Column("fiber_id", sa.String(36), nullable=False),
        sa.Column("lookup_name", sa.String(128), nullable=False),
        sa.Column("source_entry_id", sa.String(36), nullable=True),
        sa.Column("source_value", sa.String(512), nullable=True),
        sa.Column("dest_entry_id", sa.String(36), nullable=True),
        sa.Column("dest_row", sa.JSON, nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("mapped_by", sa.String(16), nullable=False, server_default="ai"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
