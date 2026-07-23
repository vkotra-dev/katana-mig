"""add data_profile JSON column to source_slices

Revision ID: 0037
Revises: 0036
Create Date: 2026-07-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('source_slices', sa.Column('data_profile', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('source_slices', 'data_profile')
