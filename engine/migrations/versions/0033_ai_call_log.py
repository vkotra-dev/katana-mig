"""add ai_call_log table

Revision ID: 0033
Revises: 0032
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"


def upgrade() -> None:
    op.create_table(
        "ai_call_log",
        sa.Column("call_id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("project_registry.project_id"),
            nullable=False,
        ),
        sa.Column("call_type", sa.String(64), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=True),
        sa.Column("model_id", sa.String(128), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "called_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_ai_call_log_project_id", "ai_call_log", ["project_id"])
    op.create_index("ix_ai_call_log_artifact_id", "ai_call_log", ["artifact_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_call_log_artifact_id", table_name="ai_call_log")
    op.drop_index("ix_ai_call_log_project_id", table_name="ai_call_log")
    op.drop_table("ai_call_log")
