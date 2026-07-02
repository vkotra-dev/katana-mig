"""add notifications table

Revision ID: 0017_notifications
Revises: 0016_project_schema_analysis
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_notifications"
down_revision = "0016_project_schema_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project_registry.project_id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("deep_link", sa.String(1024), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_project_id", "notifications", ["project_id"])
    op.create_index("ix_notifications_event_type", "notifications", ["event_type"])
    op.create_index("ix_notifications_read", "notifications", ["read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_read", table_name="notifications")
    op.drop_index("ix_notifications_event_type", table_name="notifications")
    op.drop_index("ix_notifications_project_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
