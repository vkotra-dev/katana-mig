"""add dry_run_artifacts table

Revision ID: 0021_dry_run_artifact
Revises: 0020_feed_comments
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_dry_run_artifact"
down_revision = "0020_feed_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dry_run_artifacts",
        sa.Column("dry_run_artifact_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("run_records.run_id"), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project_registry.project_id"), nullable=False),
        sa.Column("destination_object_name", sa.String(length=255), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("field_coverage_pct", sa.Float(), nullable=True),
        sa.Column("pii_fields", sa.JSON(), nullable=False),
        sa.Column("sample_rows", sa.JSON(), nullable=False),
        sa.Column("failures", sa.JSON(), nullable=False),
        sa.Column("push_back_comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dry_run_artifacts_run_id", "dry_run_artifacts", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_dry_run_artifacts_run_id", table_name="dry_run_artifacts")
    op.drop_table("dry_run_artifacts")
