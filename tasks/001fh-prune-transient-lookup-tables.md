# Task 001fh: Alembic Migration & Prune Deprecated Transient Lookup Tables

- **Plan**: [2026-07-24-001fh-prune-transient-lookup-tables.md](../plans/2026-07-24-001fh-prune-transient-lookup-tables.md)
- **Domain**: [governance.md](../docs/domain/governance.md)

## Objective
Create Alembic migration `0039_drop_transient_lookup_tables.py` to drop the 4 deprecated transient lookup tables (`lookup_mappings`, `lookup_dest_entries`, `lookup_dest_feeds`, `lookup_source_entries`) and remove deprecated ORM models from `db/models.py`.

## Requirements
1. Create Alembic migration `0039_drop_transient_lookup_tables.py`.
2. Delete ORM models `LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, `LookupMapping` from `db/models.py`.
3. Clean up deprecated sub-resource schemas in `api/schemas.py`.
4. Verify full backend and frontend test suite health (694+ tests pass 100%).
