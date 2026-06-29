"""add change requests and approval records

Revision ID: 0002_change_requests_and_approvals
Revises: 0001_initial_schema
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_change_requests"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "change_requests",
        sa.Column("change_request_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("change_request_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project_registry.project_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
    )
    op.create_index(op.f("ix_change_requests_project_id"), "change_requests", ["project_id"], unique=False)

    op.create_table(
        "approval_records",
        sa.Column("approval_record_id", sa.String(length=36), primary_key=True),
        sa.Column("change_request_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("approver_user_id", sa.String(length=36), nullable=True),
        sa.Column("approval_stage", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("decision_payload", sa.JSON(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["change_request_id"], ["change_requests.change_request_id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project_registry.project_id"]),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.user_id"]),
    )
    op.create_index(op.f("ix_approval_records_project_id"), "approval_records", ["project_id"], unique=False)
    op.create_index(
        op.f("ix_approval_records_change_request_id"),
        "approval_records",
        ["change_request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_approval_records_change_request_id"), table_name="approval_records")
    op.drop_index(op.f("ix_approval_records_project_id"), table_name="approval_records")
    op.drop_table("approval_records")
    op.drop_index(op.f("ix_change_requests_project_id"), table_name="change_requests")
    op.drop_table("change_requests")
