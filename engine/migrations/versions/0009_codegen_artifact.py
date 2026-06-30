"""add code_generation_artifacts table

Revision ID: 0009_codegen_artifact
Revises: 0008_source_intake_fields
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_codegen_artifact"
down_revision = "0008_source_intake_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "code_generation_artifacts",
        sa.Column("codegen_artifact_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("destination_object_name", sa.String(length=255), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("source_slice_version", sa.String(length=255), nullable=True),
        sa.Column("mapping_snapshot_version", sa.String(length=255), nullable=True),
        sa.Column("lookup_snapshot_version", sa.String(length=255), nullable=True),
        sa.Column("sql_bundle", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project_registry.project_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["run_records.run_id"]),
    )
    op.create_index(
        "ix_code_generation_artifacts_project_id",
        "code_generation_artifacts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_code_generation_artifacts_run_id",
        "code_generation_artifacts",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_code_generation_artifacts_run_id", table_name="code_generation_artifacts")
    op.drop_index("ix_code_generation_artifacts_project_id", table_name="code_generation_artifacts")
    op.drop_table("code_generation_artifacts")
