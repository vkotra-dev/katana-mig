"""add feed_comments table

Revision ID: 0020_feed_comments
Revises: 0019_fiber_models
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_feed_comments"
down_revision = "0019_fiber_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_comments",
        sa.Column("comment_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "feed_id",
            sa.String(length=36),
            sa.ForeignKey("feeds.source_definition_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_feed_comments_feed_id", "feed_comments", ["feed_id"])


def downgrade() -> None:
    op.drop_index("ix_feed_comments_feed_id", table_name="feed_comments")
    op.drop_table("feed_comments")
