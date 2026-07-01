"""add source value map to lookup value maps

Revision ID: 0013_lvm_source_value_map
Revises: 0012_lookup_value_maps
Create Date: 2026-06-30
"""

from __future__ import annotations

revision = "0013_lvm_source_value_map"
down_revision = "0012_lookup_value_maps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `0012` already creates the final table shape. Keep this revision as a
    # chain anchor so sequential upgrades never see the transient constraint.
    pass


def downgrade() -> None:
    pass
