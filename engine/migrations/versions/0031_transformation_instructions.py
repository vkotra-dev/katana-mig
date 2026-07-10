"""add transformation_instructions to source_definitions

Revision ID: 0031
Revises: 0030
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"

def upgrade() -> None:
    op.add_column(
        "source_definitions",
        sa.Column("transformation_instructions", sa.Text(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column("source_definitions", "transformation_instructions")
