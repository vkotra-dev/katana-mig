"""add pm_user_id to project_registry

Revision ID: 0026
Revises: 2149fa46cde2
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "2149fa46cde2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_registry",
        sa.Column("pm_user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column("project_registry", "pm_user_id")
