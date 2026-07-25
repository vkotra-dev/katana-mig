Task: tasks/completed/001gv-react-readonly-input-value-prop-warning.md
Plan: plans/2026-07-25-001gv-react-readonly-input-value-prop-warning.md
Commits: 11b2e97

## Changes Made

### `web/components/projects/LookupMappingTable.tsx`
- Source-value `<input>` (inside `group.sourceValues.map(...)`): `readOnly={!editingEnabled}` → `readOnly` (unconditional). The input has no `onChange`/`onInput` handler anywhere and was never actually editable by typing — the only ways `sourceValues` changes are the separate Add/Remove controls — so `readOnly` should not depend on `editingEnabled`. `value={srcVal}` stays controlled (not switched to `defaultValue`).

### `web/components/projects/__tests__/LookupMappingTable.test.tsx`
- Renamed and inverted the assertion in the test that previously asserted the input becomes non-readOnly when `editingEnabled` — it now asserts the input stays `readOnly` in that state, matching the corrected behavior.

## Deviations from Plan

- Mid-implementation, a working-tree state was found with the *rejected* `defaultValue` fix applied instead of the planned `readOnly`-unconditional fix (likely an earlier, superseded attempt). Caught during review before commit — reverted to the plan's actual fix and re-verified (337/337) before committing.

## Tests

`cd web && npm test -- --run` — 337 passed, 0 failed.
