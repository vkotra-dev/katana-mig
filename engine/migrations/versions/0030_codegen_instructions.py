"""add codegen_instructions to project_definitions

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"

def upgrade() -> None:
    op.add_column(
        "project_definitions",
        sa.Column("codegen_instructions", sa.Text(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column("project_definitions", "codegen_instructions")
