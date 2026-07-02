# Task 001aq — Delivery Bundle 0000/0001+ Sequencing

**Plan:** `plans/2026-07-01-001aq-bundle-sequencing.md`

## Domain

- `docs/domain/ui.md` — SQL bundle delivery section; DDL analysis prompt banner
- `docs/domain/api.md` — 0000_ prefix for lookup fibers; FK-ordered domain object sequencing

## Scope

Wire lookup fiber codegen into the delivery bundle and fix bundle ordering:

- `codegen/lookup_upsert.py` (new) — pure function `generate_lookup_upsert_sql(lookup_name, value_map, target_db_engine)` supporting PostgreSQL (`INSERT … ON CONFLICT`), MySQL (`ON DUPLICATE KEY UPDATE`), MSSQL/Oracle (`MERGE`) with single-quote escaping and deterministic row ordering
- `trigger_fiber` in `management/fibers.py` — when `fiber_type == "lookup"`, resolve latest approved `LookupSnapshot`, call `generate_lookup_upsert_sql`, create `CodeGenerationArtifact` named `0000_{fiber_key}`, set `fiber.output_sql`
- `codegen/service.py` `build_delivery_bundle_text` — split artifacts into `0000_`-prefixed (lookup, plain headings) and `0001+`-prefixed (domain objects, FK-ordered numbered headings); lookup artifacts always first

This is a later-phase delivery ticket and depends on the delivery sequencing
foundation in `001ah` plus the fiber models in `001ak`.

## Tasks (3)

1. **`codegen/lookup_upsert.py`** — pure SQL generator with 4 dialect code paths, escaping, and empty-map guard.
2. **`trigger_fiber` lookup codegen** — resolve snapshot, generate SQL, write artifact + `output_sql`, transition to `"codegen_complete"`.
3. **`build_delivery_bundle_text` ordering** — `0000_`-prefixed artifacts first (alphabetical), then FK-ordered domain artifacts (numbered from 1).

## Success criteria

- `generate_lookup_upsert_sql` produces correct SQL for all 4 dialects
- `trigger_fiber` on a lookup fiber creates a `0000_{key}` artifact
- Bundle text puts all lookup upserts before all domain DDL
- All tests pass

## Execution order

Execute after 001ah (codegen service exists) and 001ak (fiber + snapshot models).
