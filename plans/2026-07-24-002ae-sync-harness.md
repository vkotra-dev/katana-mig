---
id: 002ae
title: Sync docs/domain/harness.md against actual codebase
status: ready
created: 2026-07-24
domain: docs/domain/harness.md
task: 002ae
---

# Plan: Sync docs/domain/harness.md

## Task and Domain Links

- **Task:** [002ae](../tasks/002ae-sync-domain-docs-harness.md)
- **Domain Doc:** `docs/domain/harness.md`

## Current State

`docs/domain/harness.md` was last updated 2026-07-16. It lists 9 core harness components and 14 platform harness components, plus run loop order and lifecycle stages.

## Objective

Read `docs/domain/harness.md` section by section, cross-reference against actual files in `engine/src/migrations_engine/harness/` and `engine/src/migrations_engine/`. Verify each component file exists and describe what it actually does.

## Out of Scope

- Any other domain doc files
- Backend implementation changes

## Blast Radius

One file: `docs/domain/harness.md`

## File Changes

- `docs/domain/harness.md` — patch in-place

## Verification

1. `ls engine/src/migrations_engine/harness/*.py` — verify all 9 core components exist
2. `ls engine/src/migrations_engine/*.py` — verify platform components
3. Verify run loop order in `harness/run_manager.py`
4. Verify disposition types in `harness/failure_taxonomy.py`
5. Verify lifecycle stages in `harness/conductor.py`

## Pitfalls

- Harness components may have moved or been renamed since the doc was written
- The "14 platform harness components" may include files that no longer exist (e.g. runtime_orchestrator, domain_lexicon)
- Run loop order and disposition types are implementation details that change frequently

## Tests

N/A — documentation-only change, no test suite applies.

## Commit

```
docs(domain): sync harness.md against codebase

Cross-reference docs/domain/harness.md against actual harness components,
run manager, failure taxonomy, and conductor. Fix component names,
run loop order, disposition types, and lifecycle stages.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
