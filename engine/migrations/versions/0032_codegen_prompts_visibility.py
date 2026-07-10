"""add codegen prompts visibility columns

Revision ID: 0032
Revises: 0031
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"

def upgrade() -> None:
    op.add_column(
        "code_generation_artifacts",
        sa.Column("compiled_system_prompt", sa.Text(), nullable=True)
    )
    op.add_column(
        "code_generation_artifacts",
        sa.Column("compiled_user_prompt", sa.Text(), nullable=True)
    )
    op.add_column(
        "code_generation_artifacts",
        sa.Column("raw_llm_response", sa.Text(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column("code_generation_artifacts", "raw_llm_response")
    op.drop_column("code_generation_artifacts", "compiled_user_prompt")
    op.drop_column("code_generation_artifacts", "compiled_system_prompt")
