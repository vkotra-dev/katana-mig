"""add destination_mappings column to lookup_value_maps

Revision ID: 0040
Revises: 0039
Create Date: 2026-07-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0040"
down_revision = "0039"


def upgrade() -> None:
    # Column may already exist from partial migration run — use IF NOT EXISTS via raw SQL
    op.execute(
        "ALTER TABLE lookup_value_maps ADD COLUMN IF NOT EXISTS destination_mappings JSON NULL"
    )
    # Backfill existing rows with empty arrays
    op.execute("UPDATE lookup_value_maps SET destination_mappings = '[]' WHERE destination_mappings IS NULL")
    # Set NOT NULL after backfill
    op.execute(
        "ALTER TABLE lookup_value_maps MODIFY COLUMN destination_mappings JSON NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("lookup_value_maps", "destination_mappings")
