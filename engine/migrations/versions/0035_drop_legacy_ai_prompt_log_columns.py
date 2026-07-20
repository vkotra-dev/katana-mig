"""drop_legacy_ai_prompt_log_columns

Revision ID: 0035
Revises: 0034
Create Date: 2026-07-20 22:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("mapping_snapshots", "ai_trace")
    op.drop_column("code_generation_artifacts", "compiled_system_prompt")
    op.drop_column("code_generation_artifacts", "compiled_user_prompt")
    op.drop_column("code_generation_artifacts", "raw_llm_response")


def downgrade():
    op.add_column("code_generation_artifacts", sa.Column("raw_llm_response", sa.Text(), nullable=True))
    op.add_column("code_generation_artifacts", sa.Column("compiled_user_prompt", sa.Text(), nullable=True))
    op.add_column("code_generation_artifacts", sa.Column("compiled_system_prompt", sa.Text(), nullable=True))
    op.add_column("mapping_snapshots", sa.Column("ai_trace", sa.JSON(), nullable=True))
