# 001fa - Rewrite lookup fiber mapping to use strict ID/Value pairs

## Objective
Tighten the lookup fiber mapping logic to use explicit ID and Label (Value) pairs across the entire pipeline. The current system passes the entire reference row JSON up to the AI prompt and UI, which causes hallucination risks, bloated tokens, and highly complex UI rendering. 

We will simplify this by:
1. Extracting the `(id, label)` at the backend before processing.
2. Updating the AI prompt to only return `id`.
3. Storing only the `id` and `label` in the database for the destination row.
4. Refactoring the UI grid to display a simple `{label} ({id})` format.

## Out of Scope
- Changing the primary architecture of fibers and change requests.
- Modifying how source values are ingested.

## Plan File
[plans/2026-07-23-001fa-lookup-fiber-rewrite.md](../plans/2026-07-23-001fa-lookup-fiber-rewrite.md)
