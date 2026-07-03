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
    op.drop_column("project_registry", "lexicon_scope")
    op.add_column("project_registry", sa.Column("lexicon_scope", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_definitions", "project_resources")
    op.add_column("project_definitions", sa.Column("environment", sa.String(length=64), nullable=True))
    op.drop_column("project_registry", "lexicon_scope")
    op.add_column("project_registry", sa.Column("lexicon_scope", sa.JSON(), nullable=True))
