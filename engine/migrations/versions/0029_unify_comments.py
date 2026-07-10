"""unify comments table

Revision ID: 0029
Revises: 0028
"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"

def upgrade() -> None:
    # 1. Add source_slice_id column as nullable
    op.add_column(
        "feed_comments",
        sa.Column(
            "source_slice_id",
            sa.String(length=36),
            sa.ForeignKey("source_slices.source_slice_id", name="fk_feed_comments_source_slice_id", ondelete="CASCADE"),
            nullable=True,
        )
    )
    op.create_index("ix_feed_comments_source_slice_id", "feed_comments", ["source_slice_id"])

    # 2. Migrate existing data from feed_slice_comments to feed_comments
    # We select feed_slice_comments joined with source_slices to find the feed_id
    connection = op.get_bind()
    slice_comments = connection.execute(
        sa.text(
            "SELECT fsc.comment_id, fsc.source_slice_id, fsc.user_id, fsc.body, fsc.created_at, ss.source_definition_id "
            "FROM feed_slice_comments fsc "
            "JOIN source_slices ss ON fsc.source_slice_id = ss.source_slice_id"
        )
    ).fetchall()

    for row in slice_comments:
        connection.execute(
            sa.text(
                "INSERT INTO feed_comments (comment_id, feed_id, user_id, body, source_slice_id, created_at) "
                "VALUES (:comment_id, :feed_id, :user_id, :body, :source_slice_id, :created_at)"
            ),
            {
                "comment_id": row.comment_id,
                "source_slice_id": row.source_slice_id,
                "user_id": row.user_id,
                "body": row.body,
                "created_at": row.created_at,
                "feed_id": row.source_definition_id,
            }
        )

    # 3. Drop feed_slice_comments table
    op.drop_table("feed_slice_comments")


def downgrade() -> None:
    # Recreate feed_slice_comments table
    op.create_table(
        "feed_slice_comments",
        sa.Column("comment_id", sa.String(length=36), primary_key=True),
        sa.Column("source_slice_id", sa.String(length=36), sa.ForeignKey("source_slices.source_slice_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feed_slice_comments_source_slice_id", "feed_slice_comments", ["source_slice_id"])

    # Move comments back from feed_comments that have source_slice_id set
    connection = op.get_bind()
    slice_comments = connection.execute(
        sa.text(
            "SELECT comment_id, source_slice_id, user_id, body, created_at "
            "FROM feed_comments "
            "WHERE source_slice_id IS NOT NULL"
        )
    ).fetchall()

    for row in slice_comments:
        connection.execute(
            sa.text(
                "INSERT INTO feed_slice_comments (comment_id, source_slice_id, user_id, body, created_at) "
                "VALUES (:comment_id, :source_slice_id, :user_id, :body, :created_at)"
            ),
            {
                "comment_id": row.comment_id,
                "source_slice_id": row.source_slice_id,
                "user_id": row.user_id,
                "body": row.body,
                "created_at": row.created_at,
            }
        )

    # Delete migrated rows from feed_comments
    connection.execute(
        sa.text("DELETE FROM feed_comments WHERE source_slice_id IS NOT NULL")
    )

    # Remove source_slice_id column
    op.drop_constraint("fk_feed_comments_source_slice_id", "feed_comments", type_="foreignkey")
    op.drop_index("ix_feed_comments_source_slice_id", table_name="feed_comments")
    op.drop_column("feed_comments", "source_slice_id")
