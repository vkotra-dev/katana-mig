"""add destination_columns

Revision ID: 0036
Revises: 460c9261a905
Create Date: 2026-07-22 05:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '0036'
down_revision = '460c9261a905'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('mapping_snapshots', sa.Column('destination_columns', sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column('mapping_snapshots', 'destination_columns')
