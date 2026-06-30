"""add copybook_text, header_csv, source_slice_rows

Revision ID: 0008_source_intake_fields
Revises: 0007_mapping_lookup_snapshots
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_source_intake_fields"
down_revision = "0007_mapping_lookup_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_definitions", sa.Column("copybook_text", sa.Text(), nullable=True))
    op.add_column("source_slices", sa.Column("header_csv", sa.Text(), nullable=True))
    op.add_column("source_slices", sa.Column("approval_rejection_reason", sa.Text(), nullable=True))
    op.add_column("source_slices", sa.Column("parse_warnings", sa.JSON(), nullable=True))
    op.add_column("source_slices", sa.Column("file_storage_path", sa.String(length=255), nullable=True))

    op.create_table(
        "source_slice_rows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_slice_id", sa.String(length=36), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("row_csv", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_slice_id"], ["source_slices.source_slice_id"]),
    )
    op.create_index(
        op.f("ix_source_slice_rows_source_slice_id"),
        "source_slice_rows",
        ["source_slice_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_source_slice_rows_source_slice_id"), table_name="source_slice_rows")
    op.drop_table("source_slice_rows")
    op.drop_column("source_slices", "file_storage_path")
    op.drop_column("source_slices", "parse_warnings")
    op.drop_column("source_slices", "approval_rejection_reason")
    op.drop_column("source_slices", "header_csv")
    op.drop_column("source_definitions", "copybook_text")
