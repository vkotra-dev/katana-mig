# Plan: Task 001fh — Alembic Migration & Prune Deprecated Transient Lookup Tables

- **Task**: [001fh-prune-transient-lookup-tables.md](file:///Users/vjkotra/projects/katana/tasks/001fh-prune-transient-lookup-tables.md)
- **Domain**: [governance.md](file:///Users/vjkotra/projects/katana/docs/domain/governance.md)

---

## Current State
`LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, and `LookupMapping` tables are deprecated following Task 001fg.

---

## Objective
Create Alembic migration `0039_drop_transient_lookup_tables.py`, drop the 4 tables, and remove deprecated ORM models from `db/models.py`.

---

## Blast Radius
- `engine/src/migrations_engine/db/migrations/versions/0039_drop_transient_lookup_tables.py`
- `engine/src/migrations_engine/db/models.py`
- `engine/src/migrations_engine/api/schemas.py`

---

## Detailed Implementation Instructions for Local LLM Agent

### Step 1: Create Alembic Migration `0039_drop_transient_lookup_tables.py`
Create file in `engine/src/migrations_engine/db/migrations/versions/0039_drop_transient_lookup_tables.py`:

```python
"""drop transient lookup tables

Revision ID: 0039
Revises: 0038
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.drop_table('lookup_mappings')
    op.drop_table('lookup_dest_entries')
    op.drop_table('lookup_dest_feeds')
    op.drop_table('lookup_source_entries')

def downgrade() -> None:
    # Downgrade reinstates tables if ever needed
    op.create_table(
        'lookup_source_entries',
        sa.Column('entry_id', sa.String(36), primary_key=True),
        sa.Column('fiber_id', sa.String(36), nullable=False),
        sa.Column('lookup_name', sa.String(128), nullable=False),
        sa.Column('source_value', sa.String(512), nullable=False),
        sa.Column('discovery_type', sa.String(16), nullable=False, server_default='sample'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
```

### Step 2: Remove Deprecated Models from `db/models.py` (Lines 446–512)
Delete the 4 SQLAlchemy class definitions:
- Delete `class LookupSourceEntry(Base)`
- Delete `class LookupDestFeed(Base)`
- Delete `class LookupDestEntry(Base)`
- Delete `class LookupMapping(Base)`

### Step 3: Clean up API Schemas in `api/schemas.py`
Remove deprecated sub-resource schemas:
- Delete `LookupSourceEntryResponse`
- Delete `LookupDestFeedResponse`
- Delete `LookupDestEntryResponse`
- Delete `LookupMappingResponse`

---

## Tests
```bash
# Backend test suite
cd engine && source ../.venv/bin/activate && pytest -v

# Frontend test suite
cd web && npm run test
```

---

## Verification Checklist
- [ ] Alembic migration `0039` executes cleanly.
- [ ] ORM models removed from `models.py`.
- [ ] Full 694+ test suite across backend and frontend passes 100%.

---

## Commit
`db(migrations): drop deprecated transient lookup tables and prune ORM models (0039, 001fh)`
