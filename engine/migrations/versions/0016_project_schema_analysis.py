"""add project schema analysis table

Revision ID: 0016_project_schema_analysis
Revises: 0015_reconciliation_tables
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_project_schema_analysis"
down_revision = "0015_reconciliation_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_schema_analyses",
        sa.Column("analysis_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project_definitions.project_id"), nullable=False, unique=True),
        sa.Column("destination_object_sequence", sa.JSON(), nullable=False),
        sa.Column("identified_count", sa.Integer(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_schema_analyses_project_id", "project_schema_analyses", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_schema_analyses_project_id", table_name="project_schema_analyses")
    op.drop_table("project_schema_analyses")
