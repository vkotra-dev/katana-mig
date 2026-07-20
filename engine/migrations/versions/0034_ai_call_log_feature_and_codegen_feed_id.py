"""ai_call_log_feature_and_codegen_feed_id

Revision ID: 0034
Revises: 0033
Create Date: 2026-07-20 17:52:24.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add feature column to ai_call_log with a default to avoid null constraint failures on existing rows
    op.add_column("ai_call_log", sa.Column("feature", sa.String(32), nullable=False, server_default="feed_mapping"))
    
    # Data migration: backfill feature based on call_type
    op.execute("""
        UPDATE ai_call_log
        SET feature = 'codegen'
        WHERE call_type IN ('schema_analysis', 'codegen')
    """)
    op.execute("""
        UPDATE ai_call_log
        SET feature = 'feed_mapping'
        WHERE call_type NOT IN ('schema_analysis', 'codegen')
    """)

    # Drop the server default now that backfill is done
    op.alter_column("ai_call_log", "feature", server_default=None)

    op.create_index(op.f("ix_ai_call_log_feature"), "ai_call_log", ["feature"], unique=False)

    # 2. Add source_definition_id to code_generation_artifacts
    op.add_column("code_generation_artifacts", sa.Column("source_definition_id", sa.String(36), sa.ForeignKey("source_definitions.source_definition_id"), nullable=True))
    op.create_index(op.f("ix_code_generation_artifacts_source_definition_id"), "code_generation_artifacts", ["source_definition_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_code_generation_artifacts_source_definition_id"), table_name="code_generation_artifacts")
    op.drop_column("code_generation_artifacts", "source_definition_id")

    op.drop_index(op.f("ix_ai_call_log_feature"), table_name="ai_call_log")
    op.drop_column("ai_call_log", "feature")
