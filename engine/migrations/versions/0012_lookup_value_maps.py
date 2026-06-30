"""add lookup value maps

Revision ID: 0012_lookup_value_maps
Revises: 0011_source_analysis_artifacts
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_lookup_value_maps"
down_revision = "0011_source_analysis_artifacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lookup_value_maps",
        sa.Column("lookup_value_map_id", sa.String(length=36), primary_key=True),
        sa.Column("source_definition_id", sa.String(length=36), nullable=False),
        sa.Column("lookup_name", sa.String(length=128), nullable=False),
        sa.Column("destination_table", sa.JSON(), nullable=False),
        sa.Column(
            "source_value_map",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_definition_id"], ["source_definitions.source_definition_id"]),
    )


def downgrade() -> None:
    op.drop_table("lookup_value_maps")
