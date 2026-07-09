"""add feed_slice_comments table

Revision ID: 0028
Revises: 0027
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"

def upgrade() -> None:
    op.create_table(
        "feed_slice_comments",
        sa.Column("comment_id", sa.String(length=36), primary_key=True),
        sa.Column("source_slice_id", sa.String(length=36), sa.ForeignKey("source_slices.source_slice_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_feed_slice_comments_source_slice_id", "feed_slice_comments", ["source_slice_id"])

def downgrade() -> None:
    op.drop_table("feed_slice_comments")
