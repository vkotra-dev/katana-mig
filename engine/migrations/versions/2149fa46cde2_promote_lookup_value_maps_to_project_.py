"""promote lookup value maps to project scope

Revision ID: 2149fa46cde2
Revises: 0025_feed_hints_and_ai_trace
Create Date: 2026-07-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "2149fa46cde2"
down_revision = "0025_feed_hints_and_ai_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add project_id column (nullable initially for backfill)
    op.add_column("lookup_value_maps",
        sa.Column("project_id", sa.String(36), nullable=True)
    )

    # 2. Backfill from source_definitions
    op.execute("""
        UPDATE lookup_value_maps lvm
        JOIN source_definitions sd ON lvm.source_definition_id = sd.source_definition_id
        SET lvm.project_id = sd.project_id
    """)

    # 3. Dedup: for any (project_id, lookup_name) collision keep the newest row
    op.execute("""
        DELETE lvm1 FROM lookup_value_maps lvm1
        INNER JOIN lookup_value_maps lvm2
          ON lvm1.project_id = lvm2.project_id
          AND lvm1.lookup_name = lvm2.lookup_name
          AND lvm1.created_at < lvm2.created_at
    """)

    # 4. Make project_id NOT NULL
    op.alter_column("lookup_value_maps", "project_id", existing_type=sa.String(36), nullable=False)

    # 5. Drop old foreign key constraint and column source_definition_id
    op.drop_constraint("lookup_value_maps_ibfk_1", "lookup_value_maps", type_="foreignkey")
    op.drop_column("lookup_value_maps", "source_definition_id")

    # 6. Add new unique constraint
    op.create_unique_constraint(
        "uq_lookup_value_maps_project_name",
        "lookup_value_maps",
        ["project_id", "lookup_name"],
    )

    # 7. Add foreign key constraint on project_id
    op.create_foreign_key(
        "fk_lookup_value_maps_project_id",
        "lookup_value_maps",
        "project_registry",
        ["project_id"],
        ["project_id"],
    )


def downgrade() -> None:
    # 1. Re-add source_definition_id column
    op.add_column("lookup_value_maps",
        sa.Column("source_definition_id", sa.String(36), nullable=True)
    )

    # 2. Drop new constraints
    op.drop_constraint("fk_lookup_value_maps_project_id", "lookup_value_maps", type_="foreignkey")
    op.drop_constraint("uq_lookup_value_maps_project_name", "lookup_value_maps", type_="unique")

    # 3. Backfill source_definition_id where possible
    op.execute("""
        UPDATE lookup_value_maps lvm
        JOIN source_definitions sd ON lvm.project_id = sd.project_id
        SET lvm.source_definition_id = sd.source_definition_id
    """)

    # 4. Make source_definition_id NOT NULL (dummy value fallback if no match found during downgrade)
    op.execute("UPDATE lookup_value_maps SET source_definition_id = 'placeholder' WHERE source_definition_id IS NULL")
    op.alter_column("lookup_value_maps", "source_definition_id", existing_type=sa.String(36), nullable=False)

    # 5. Drop project_id column
    op.drop_column("lookup_value_maps", "project_id")

    # 6. Re-add foreign key on source_definition_id
    op.create_foreign_key(
        "lookup_value_maps_ibfk_1",
        "lookup_value_maps",
        "source_definitions",
        ["source_definition_id"],
        ["source_definition_id"],
    )
