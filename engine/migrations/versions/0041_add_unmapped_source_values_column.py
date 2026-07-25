"""add unmapped_source_values column to lookup_value_maps

Revision ID: 0041
Revises: 0040
Create Date: 2026-07-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("lookup_value_maps")]
    if "unmapped_source_values" not in columns:
        op.add_column("lookup_value_maps", sa.Column("unmapped_source_values", sa.JSON(), nullable=True))
    op.execute("UPDATE lookup_value_maps SET unmapped_source_values = '[]' WHERE unmapped_source_values IS NULL")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("lookup_value_maps")]
    if "unmapped_source_values" in columns:
        op.drop_column("lookup_value_maps", "unmapped_source_values")
