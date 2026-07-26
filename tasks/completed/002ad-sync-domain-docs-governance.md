---
id: 002ad
title: Sync docs/domain/governance.md against actual codebase
status: done
created: 2026-07-24
priority: medium
domain: docs
depends-on: []
---

# Sync docs/domain/governance.md

## Objective

Update `docs/domain/governance.md` to accurately reflect the current repository structure, invariants, and conventions. Last updated 2026-07-20.

## Scope

- `docs/domain/governance.md` only

## What to verify

1. **Safety invariants (I1-I22)** — Verify all 22 invariants are still accurate:
   - I19-I22 (role/model invariants) — verify against actual route guards
   - I22 (domain doc currency) — this task fulfills that invariant
2. **Build order stages** — Verify all 24 stages listed match actual components:
   - Check each component file exists at the listed path
   - Check `harness/` directory has all listed files
   - Check `migration/` directory has all listed files
3. **Repository map** — Verify file tree is accurate:
   - Check `engine/src/migrations_engine/` directory structure
   - Check `web/` directory structure
   - Verify all listed files still exist
4. **Task workflow** — Verify task mechanics (numbering, paths, lifecycle) match actual convention
5. **DDL change rule** — Verify migration convention matches actual `engine/migrations/versions/`
6. **AI model policy** — Verify `engine/config/engine.yaml` and adapter layer still match described behavior

## Out of scope

- Any other domain doc files
- Backend implementation changes

## Acceptance criteria

- [x] All 22 invariants are accurate
- [x] Build order stages match actual components
- [x] Repository map is current
- [x] Task workflow rules match actual convention
- [x] DDL change rule matches actual migration pattern
- [x] Changelog updated
- [x] timestamp updated
