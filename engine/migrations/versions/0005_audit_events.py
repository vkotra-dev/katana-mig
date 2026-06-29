"""add audit events

Revision ID: 0005_audit_events
Revises: 0004_source_definitions_and_slices
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_audit_events"
down_revision = "0004_source_definitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("audit_event_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("change_request_id", sa.String(length=36), nullable=True),
        sa.Column("approval_record_id", sa.String(length=36), nullable=True),
        sa.Column("source_definition_id", sa.String(length=36), nullable=True),
        sa.Column("source_slice_id", sa.String(length=36), nullable=True),
        sa.Column("event_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project_registry.project_id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["run_records.run_id"]),
        sa.ForeignKeyConstraint(["change_request_id"], ["change_requests.change_request_id"]),
        sa.ForeignKeyConstraint(["approval_record_id"], ["approval_records.approval_record_id"]),
        sa.ForeignKeyConstraint(["source_definition_id"], ["source_definitions.source_definition_id"]),
        sa.ForeignKeyConstraint(["source_slice_id"], ["source_slices.source_slice_id"]),
    )
    op.create_index(op.f("ix_audit_events_project_id"), "audit_events", ["project_id"], unique=False)
    op.create_index(op.f("ix_audit_events_run_id"), "audit_events", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_audit_events_change_request_id"), "audit_events", ["change_request_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_change_request_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_run_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_project_id"), table_name="audit_events")
    op.drop_table("audit_events")
