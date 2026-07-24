# Plan: Task 001fh — Alembic Migration & Prune Deprecated Transient Lookup Tables

- **Task**: [001fh-prune-transient-lookup-tables.md](file:///Users/vjkotra/projects/katana/tasks/001fh-prune-transient-lookup-tables.md)
- **Domain**: [governance.md](file:///Users/vjkotra/projects/katana/docs/domain/governance.md)

---

## Current State
`LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, and `LookupMapping` tables are deprecated following Task 001fg.

---

## Objective
Create Alembic migration `0039_drop_transient_lookup_tables.py`, drop the 4 tables, and remove ORM models from `db/models.py`.

---

## Blast Radius
- `engine/src/migrations_engine/db/migrations/versions/0039_drop_transient_lookup_tables.py`
- `engine/src/migrations_engine/db/models.py`
- `engine/src/migrations_engine/api/schemas.py`

---

## Tests
```bash
# Backend suite
cd engine && source ../.venv/bin/activate && pytest -v

# Frontend suite
cd web && npm run test
```

---

## Commit
`db(migrations): drop deprecated transient lookup tables and prune ORM models (0039, 001fh)`
