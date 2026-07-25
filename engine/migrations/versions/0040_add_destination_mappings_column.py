"""add destination_mappings column to lookup_value_maps

Revision ID: 0040
Revises: 0039
Create Date: 2026-07-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("lookup_value_maps")]
    if "destination_mappings" not in columns:
        op.add_column("lookup_value_maps", sa.Column("destination_mappings", sa.JSON(), nullable=True))
    op.execute("UPDATE lookup_value_maps SET destination_mappings = '[]' WHERE destination_mappings IS NULL")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("lookup_value_maps")]
    if "destination_mappings" in columns:
        op.drop_column("lookup_value_maps", "destination_mappings")
