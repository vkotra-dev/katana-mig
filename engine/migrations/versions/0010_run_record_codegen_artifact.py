"""add codegen_artifact_id to run_records

Revision ID: 0010_run_record_codegen_artifact
Revises: 0009_codegen_artifact
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_run_record_codegen_artifact"
down_revision = "0009_codegen_artifact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_records",
        sa.Column("codegen_artifact_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("run_records", "codegen_artifact_id")
