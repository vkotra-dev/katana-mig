"""add version_history table

Revision ID: 0043
Revises: 0042
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"


def upgrade() -> None:
    op.create_table(
        "version_history",
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False, index=True),
        sa.Column("entity_id", sa.String(36), nullable=False, index=True),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(36), nullable=True, index=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_version_history_entity",
        "version_history",
        ["entity_type", "entity_id", "field_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_version_history_entity", table_name="version_history")
    op.drop_table("version_history")
