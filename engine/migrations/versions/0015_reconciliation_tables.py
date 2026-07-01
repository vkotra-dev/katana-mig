"""add reconciliation reports and lineage tables

Revision ID: 0015_reconciliation_tables
Revises: 0014_run_record_lookup_snapshot_versions
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_reconciliation_tables"
down_revision = "0014_run_record_lookup_snapshot_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_reports",
        sa.Column("report_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("run_records.run_id"), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("overall_status", sa.String(16), nullable=False, server_default=sa.text("'in_progress'")),
        sa.Column("row_count_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reconciliation_reports_run_id", "reconciliation_reports", ["run_id"])

    op.create_table(
        "reconciliation_lineage_rows",
        sa.Column("lineage_row_id", sa.String(36), primary_key=True),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reconciliation_reports.report_id"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("run_records.run_id"), nullable=False),
        sa.Column("source_row_index", sa.Integer(), nullable=True),
        sa.Column("source_row_key", sa.String(255), nullable=True),
        sa.Column("destination_row_id", sa.String(255), nullable=True),
        sa.Column("mapping_rules_applied", sa.JSON(), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("outcome_detail", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reconciliation_lineage_rows_report_id", "reconciliation_lineage_rows", ["report_id"])
    op.create_index("ix_reconciliation_lineage_rows_run_id", "reconciliation_lineage_rows", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_reconciliation_lineage_rows_run_id", table_name="reconciliation_lineage_rows")
    op.drop_index("ix_reconciliation_lineage_rows_report_id", table_name="reconciliation_lineage_rows")
    op.drop_table("reconciliation_lineage_rows")
    op.drop_index("ix_reconciliation_reports_run_id", table_name="reconciliation_reports")
    op.drop_table("reconciliation_reports")
