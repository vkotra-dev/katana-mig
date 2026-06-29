"""add source definitions and source slices

Revision ID: 0004_source_definitions_and_slices
Revises: 0003_runs_and_checkpoints
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_source_definitions"
down_revision = "0003_runs_and_checkpoints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_definitions",
        sa.Column("source_definition_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_contract_version", sa.String(length=64), nullable=False),
        sa.Column("access_reference", sa.String(length=255), nullable=True),
        sa.Column("selection_information", sa.JSON(), nullable=True),
        sa.Column("layout_information", sa.JSON(), nullable=True),
        sa.Column("destination_object_references", sa.JSON(), nullable=True),
        sa.Column("sample_policy", sa.JSON(), nullable=True),
        sa.Column("source_details", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project_registry.project_id"]),
    )
    op.create_index(op.f("ix_source_definitions_project_id"), "source_definitions", ["project_id"], unique=False)

    op.create_table(
        "source_slices",
        sa.Column("source_slice_id", sa.String(length=36), primary_key=True),
        sa.Column("source_definition_id", sa.String(length=36), nullable=False),
        sa.Column("source_contract_version", sa.String(length=64), nullable=False),
        sa.Column("source_slice_version", sa.String(length=64), nullable=False),
        sa.Column("source_schema_artifact", sa.JSON(), nullable=True),
        sa.Column("masking_policy", sa.JSON(), nullable=True),
        sa.Column("slice_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_definition_id"], ["source_definitions.source_definition_id"]),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.user_id"]),
        sa.UniqueConstraint("source_definition_id", "source_slice_version"),
    )
    op.create_index(op.f("ix_source_slices_source_definition_id"), "source_slices", ["source_definition_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_source_slices_source_definition_id"), table_name="source_slices")
    op.drop_table("source_slices")
    op.drop_index(op.f("ix_source_definitions_project_id"), table_name="source_definitions")
    op.drop_table("source_definitions")
