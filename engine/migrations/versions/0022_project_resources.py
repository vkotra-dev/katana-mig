"""project_resources and lexicon_scope fields

Revision ID: 0022_project_resources
Revises: 0021_dry_run_artifact
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0022_project_resources"
down_revision = "0021_dry_run_artifact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("project_definitions", "environment")
    op.add_column("project_definitions", sa.Column("project_resources", sa.Text(), nullable=True))
    with op.batch_alter_table("project_registry") as batch_op:
        batch_op.alter_column("lexicon_scope", type_=sa.Text(), existing_type=sa.JSON())


def downgrade() -> None:
    op.drop_column("project_definitions", "project_resources")
    op.add_column("project_definitions", sa.Column("environment", sa.String(length=64), nullable=True))
    with op.batch_alter_table("project_registry") as batch_op:
        batch_op.alter_column("lexicon_scope", type_=sa.JSON(), existing_type=sa.Text())
