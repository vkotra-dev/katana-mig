"""add source value map to lookup value maps

Revision ID: 0013_lookup_value_map_source_value_map
Revises: 0012_lookup_value_maps
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013_lookup_value_map_source_value_map"
down_revision = "0012_lookup_value_maps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_lookup_value_maps_definition_lookup_status",
        "lookup_value_maps",
        type_="unique",
    )
    op.add_column(
        "lookup_value_maps",
        sa.Column(
            "source_value_map",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("lookup_value_maps", "source_value_map")
    op.create_unique_constraint(
        "uq_lookup_value_maps_definition_lookup_status",
        "lookup_value_maps",
        ["source_definition_id", "lookup_name", "status"],
    )
