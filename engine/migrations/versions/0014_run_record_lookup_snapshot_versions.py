"""add lookup snapshot versions and codegen fk to run_records

Revision ID: 0014_run_record_lookup_snapshot_versions
Revises: 0013_lookup_value_map_source_value_map
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_run_record_lookup_snapshot_versions"
down_revision = "0013_lookup_value_map_source_value_map"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_records",
        sa.Column("lookup_snapshot_versions", sa.JSON(), nullable=True),
    )
    op.create_foreign_key(
        "fk_run_records_codegen_artifact_id",
        "run_records",
        "code_generation_artifacts",
        ["codegen_artifact_id"],
        ["codegen_artifact_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_run_records_codegen_artifact_id", "run_records", type_="foreignkey")
    op.drop_column("run_records", "lookup_snapshot_versions")
