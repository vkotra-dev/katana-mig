"""add source analysis artifacts

Revision ID: 0011_source_analysis_artifacts
Revises: 0010_run_record_codegen_artifact
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_source_analysis_artifacts"
down_revision = "0010_run_record_codegen_artifact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_schema_artifacts",
        sa.Column("schema_artifact_id", sa.String(length=36), primary_key=True),
        sa.Column("source_definition_id", sa.String(length=36), nullable=False),
        sa.Column("source_slice_version", sa.String(length=64), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_definition_id"], ["source_definitions.source_definition_id"]),
        sa.UniqueConstraint(
            "source_definition_id",
            "source_slice_version",
            name="uq_source_schema_artifacts_definition_version",
        ),
    )
    op.create_table(
        "source_value_summaries",
        sa.Column("summary_id", sa.String(length=36), primary_key=True),
        sa.Column("source_definition_id", sa.String(length=36), nullable=False),
        sa.Column("source_slice_version", sa.String(length=64), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("value_counts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_definition_id"], ["source_definitions.source_definition_id"]),
        sa.UniqueConstraint(
            "source_definition_id",
            "source_slice_version",
            "field_name",
            name="uq_source_value_summaries_definition_version_field",
        ),
    )


def downgrade() -> None:
    op.drop_table("source_value_summaries")
    op.drop_table("source_schema_artifacts")
