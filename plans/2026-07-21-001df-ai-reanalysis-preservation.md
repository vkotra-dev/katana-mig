# Plan: AI Re-analysis and Sign-off Preservation

**Task:** [001df-ai-reanalysis-preservation.md](../tasks/001df-ai-reanalysis-preservation.md)  
**Domain:** [source-model.md](../docs/domain/source-model.md) / [harness.md](../docs/domain/harness.md)

## Current State
When users click "AI Analyze Feed Slice", "AI Propose Mapping", or "AI Analyze Lookup Fiber":
1. The backend either early-exits and refuses to run if any data exists.
2. Or it destructively deletes existing mappings, permanently wiping out user sign-offs.

## Objective
Remove early-exit caches so that the AI can always be re-triggered. Introduce **upsert** logic that explicitly filters out or preserves mappings that have already been signed off by human reviewers.

## Out of Scope
- Changing the AI prompts or underlying LLM generation logic.
- UI changes (all changes are strictly backend mapping logic).

## Blast Radius
- `engine/src/migrations_engine/management/source_analysis.py` (Source Analysis)
- `engine/src/migrations_engine/mapping/review.py` (Field Mapping)
- `engine/src/migrations_engine/management/fibers.py` (Lookup Fiber)

## File Changes
1. **`source_analysis.py`**:
   - Delete the `if existing_artifact is not None: return` check.
   - Execute `db.execute(delete(SourceSchemaArtifact).where(...))` for the specific slice version before writing the new one.
2. **`mapping/review.py`**:
   - Query `MappingSignOff` for the feed.
   - Filter `SnapshotRow` generation to exclude any destination columns that exist in the sign-off list.
3. **`fibers.py`**:
   - Remove the `if has_sign_off: raise AuthApiError` block in `submit_lookup_inputs`.
   - Instead of unconditional `delete()`, query existing `LookupMapping`s where `status == "approved"`.
   - When generating new entries, exclude source values that already have an approved mapping.

## Tests
- Ensure `mypy --strict` passes.
- Ensure all automated tests (`npm test` in web, `pytest` in engine if available) continue to pass.

## Verification
1. Re-running Source Analysis generates new AI logs instead of silently skipping.
2. Proposing a mapping does not generate a proposal row for a field that is signed off.
3. Re-analyzing a lookup fiber updates unapproved rows while preserving approved rows and their sign-offs.

## Pitfalls
- Deleting the `LookupDestFeed` unconditionally breaks `LookupDestEntry` foreign keys for signed-off lookups. The new logic must carefully retain the old dest feed or ensure signed-off mappings aren't orphaned.
- For field mapping, we must ensure the UI gracefully handles snapshot rows that only contain a subset of fields (it currently does).

## Commit
- `feat: implement ai re-analysis upsert and sign-off preservation`
