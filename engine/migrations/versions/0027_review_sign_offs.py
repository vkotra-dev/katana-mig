"""add current_ball_role to mapping_snapshots, add sign-off tables

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"

def upgrade() -> None:
    op.add_column(
        "mapping_snapshots",
        sa.Column("current_ball_role", sa.String(length=50), nullable=True),
    )

    op.create_table(
        "mapping_binding_sign_offs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mapping_snapshot_id", sa.String(length=36), sa.ForeignKey("mapping_snapshots.mapping_snapshot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_object_name", sa.String(length=255), nullable=False),
        sa.Column("source_field", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("mapping_snapshot_id", "destination_object_name", "source_field", "user_id", name="uq_mapping_binding_sign_off"),
    )
    op.create_index("ix_mapping_binding_sign_offs_snapshot", "mapping_binding_sign_offs", ["mapping_snapshot_id"])

    op.create_table(
        "lookup_sign_offs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("lookup_value_map_id", sa.String(length=36), sa.ForeignKey("lookup_value_maps.lookup_value_map_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lookup_value_map_id", "user_id", name="uq_lookup_sign_off"),
    )
    op.create_index("ix_lookup_sign_offs_map", "lookup_sign_offs", ["lookup_value_map_id"])

def downgrade() -> None:
    op.drop_column("mapping_snapshots", "current_ball_role")
    op.drop_table("mapping_binding_sign_offs")
    op.drop_table("lookup_sign_offs")
