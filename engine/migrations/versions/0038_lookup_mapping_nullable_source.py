"""make lookup_mapping source_entry_id and source_value nullable

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("lookup_mappings") as batch_op:
        batch_op.alter_column("source_entry_id", existing_type=sa.VARCHAR(36), nullable=True)
        batch_op.alter_column("source_value", existing_type=sa.VARCHAR(512), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE lookup_mappings SET source_value = '' WHERE source_value IS NULL")
    op.execute("UPDATE lookup_mappings SET source_entry_id = '' WHERE source_entry_id IS NULL")
    with op.batch_alter_table("lookup_mappings") as batch_op:
        batch_op.alter_column("source_entry_id", existing_type=sa.VARCHAR(36), nullable=False)
        batch_op.alter_column("source_value", existing_type=sa.VARCHAR(512), nullable=False)
