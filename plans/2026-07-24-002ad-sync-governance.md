---
id: 002ad
title: Sync docs/domain/governance.md against actual codebase
status: ready
created: 2026-07-24
domain: docs/domain/governance.md
task: 002ad
---

# Plan: Sync docs/domain/governance.md

## Task and Domain Links

- **Task:** [002ad](../tasks/002ad-sync-domain-docs-governance.md)
- **Domain Doc:** `docs/domain/governance.md`

## Current State

`docs/domain/governance.md` was last updated 2026-07-20. It lists 22 invariants, a build order with 24 stages, and a repository map.

## Objective

Read `docs/domain/governance.md` section by section, cross-reference against actual codebase structure. Verify each invariant, each build order stage, and each file in the repository map.

## Out of Scope

- Any other domain doc files
- Backend implementation changes

## Blast Radius

One file: `docs/domain/governance.md`

## File Changes

- `docs/domain/governance.md` — patch in-place

## Verification

1. For each invariant I1-I22, verify it still applies to the current code
2. For each build order stage, verify the file exists at the listed path
3. For the repository map, verify each file path exists
4. For the DDL change rule, verify it matches actual migration patterns

## Pitfalls

- I22 (domain doc currency) is what this task fulfills
- Some harness/migration components may have moved since the doc was written
- The invariant numbering (I1-I22) needs to be verified sequentially

## Commit

```
docs(domain): sync governance.md against codebase

Cross-reference docs/domain/governance.md against actual codebase.
Fix invariant accuracy, build order stage paths, repository map,
and task workflow conventions.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
