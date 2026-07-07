"""feed hints and ai trace

Revision ID: 0025_feed_hints_and_ai_trace
Revises: 0024_mapping_per_feed
Create Date: 2026-07-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_feed_hints_and_ai_trace"
down_revision = "0024_mapping_per_feed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_definitions", sa.Column("mapping_hints", sa.Text(), nullable=True))
    op.add_column("mapping_snapshots", sa.Column("ai_trace", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("mapping_snapshots", "ai_trace")
    op.drop_column("source_definitions", "mapping_hints")
