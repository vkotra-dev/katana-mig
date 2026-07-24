# Plan: Task 001fg — Refactor Fiber AI Discovery to ProjectFiber.proposed_mappings JSON

- **Task**: [001fg-refactor-lookup-fiber-to-json.md](file:///Users/vjkotra/projects/katana/tasks/001fg-refactor-lookup-fiber-to-json.md)
- **Domain**: [governance.md](file:///Users/vjkotra/projects/katana/docs/domain/governance.md)

---

## Current State
`_analyze_lookup_fiber()` writes transient proposal data into 4 relational tables (`LookupSourceEntry`, `LookupDestFeed`, `LookupDestEntry`, `LookupMapping`).

---

## Objective
Refactor `fibers.py` to write AI lookup proposals directly into `ProjectFiber.proposed_mappings` (`JSON list[dict]`), eliminating SQL inserts into the 4 transient tables.

---

## Out of Scope
- Dropping ORM models from `db/models.py` (handled in Task 001fh).
- Alembic database migration (handled in Task 001fh).

---

## Blast Radius
- `engine/src/migrations_engine/management/fibers.py`
- `engine/src/migrations_engine/routes/fibers.py`
- `engine/tests/test_lookup_fiber_api.py`

---

## Tests
```bash
cd engine && source ../.venv/bin/activate && pytest -v
```

---

## Commit
`refactor(fibers): store lookup proposals directly in ProjectFiber proposed_mappings JSON (001fg)`
