"""add run records and run checkpoints

Revision ID: 0003_runs_and_checkpoints
Revises: 0002_change_requests_and_approvals
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_runs_and_checkpoints"
down_revision = "0002_change_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_records",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("destination_object_name", sa.String(length=255), nullable=False),
        sa.Column("source_definition_reference", sa.String(length=36), nullable=True),
        sa.Column("source_slice_version", sa.String(length=36), nullable=True),
        sa.Column("mapping_snapshot_version", sa.String(length=36), nullable=True),
        sa.Column("lookup_snapshot_version", sa.String(length=36), nullable=True),
        sa.Column("code_generation_input_snapshot_version", sa.String(length=36), nullable=True),
        sa.Column("knowledge_freeze_version", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("approvals", sa.JSON(), nullable=True),
        sa.Column("environment", sa.String(length=64), nullable=True),
        sa.Column("start_metadata", sa.JSON(), nullable=True),
        sa.Column("pause_metadata", sa.JSON(), nullable=True),
        sa.Column("resume_metadata", sa.JSON(), nullable=True),
        sa.Column("completion_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project_registry.project_id"]),
    )
    op.create_index(op.f("ix_run_records_project_id"), "run_records", ["project_id"], unique=False)

    op.create_table(
        "run_checkpoints",
        sa.Column("run_checkpoint_id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("current_object", sa.String(length=255), nullable=True),
        sa.Column("current_environment", sa.String(length=64), nullable=True),
        sa.Column("approved_snapshots", sa.JSON(), nullable=True),
        sa.Column("last_completed_checkpoint_boundary", sa.String(length=255), nullable=True),
        sa.Column("pause_reason", sa.Text(), nullable=True),
        sa.Column("checkpoint_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["run_records.run_id"]),
    )
    op.create_index(op.f("ix_run_checkpoints_run_id"), "run_checkpoints", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_run_checkpoints_run_id"), table_name="run_checkpoints")
    op.drop_table("run_checkpoints")
    op.drop_index(op.f("ix_run_records_project_id"), table_name="run_records")
    op.drop_table("run_records")
