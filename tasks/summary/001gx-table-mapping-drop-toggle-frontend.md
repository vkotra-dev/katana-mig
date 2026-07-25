Task: tasks/completed/001gx-table-mapping-drop-toggle-frontend.md
Plan: plans/2026-07-25-001gx-table-mapping-drop-toggle-frontend.md
Commits: c7a0728, 63eea96

## Changes Made

### `web/lib/mapping-api.ts`
- `dropped?: boolean` added to `MappingFieldBindingRecord`, `MappingSnapshotRaw`'s field_bindings shape, `mapMappingSnapshotResponse`'s mapping, and `patchMappingSnapshot`'s request-body construction (optional on the input type, so the existing untouched test call in `mapping-api.test.ts:193-195` keeps compiling).

### `web/components/projects/ReviewGrid.tsx`
- `MappingTableRecord.bindings[].dropped?: boolean` added.
- `onRemoveSourceField` prop renamed to `onToggleSourceField(tableName, sourceField, dropped)`.
- × hard-delete button replaced with a native `<input type="checkbox">` — always rendered (no `editingEnabled` visibility gate), `disabled={!editingEnabled}`, `checked={!group.bindings.some(b => b.dropped)}`. This is a deliberate, reasonable deviation from the plan's custom-SVG-button design — a native checkbox is more accessible by default (keyboard nav, screen reader semantics) at no extra cost.
- Source field `<span>` gets `line-through text-slate-400` when `group.bindings.some(b => b.dropped)`, otherwise `text-slate-700`.
- `AutocompleteInput` flip-upward fix: implemented via a `openUpward`/`onOpen` prop pair (parent measures and passes the boolean down) rather than the plan's internal-state design — also a reasonable deviation, though see Deviations below for a real gap this introduced.

### `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`
- `handleRemoveSourceField` → `handleToggleSourceField(tableName, sourceField, dropped)`: now maps over the *full* `fieldBindings` list (setting `dropped` only on the matching `sourceField`) instead of filtering it — this is the critical contract change that makes the backend's sign-off preservation actually work.
- `mappingTablesMap[tblName].bindings.push({...})` carries `dropped: binding.dropped ?? false` through.

### `web/components/projects/__tests__/ReviewGrid.test.tsx`, `web/app/projects/[id]/feeds/[feedId]/review/page.test.tsx`
- Both existing tests that asserted the old hard-delete/gated-visibility behavior were updated (not left alongside new ones) to assert checkbox presence, `disabled` state, and — most importantly — that `page.test.tsx`'s PATCH-payload assertion now checks the binding is *still present* with `dropped: true`, rather than absent from the array.

## Deviations from Plan

- **Fixed in follow-up commit `63eea96`**: `AutocompleteInput`'s flip-upward measurement was initially only wired to the text input's `onFocus` handler — the chevron toggle button opened the dropdown without measuring first, so clicking it directly (without prior focus) could use stale direction state from a different row. `63eea96` moves the measurement into an internal `openDropdown()` function called by both `onFocus` and the chevron's `onClick`, and removes the now-unnecessary parent-level `dropdownUpward` state and `onOpen`/`openUpward` props entirely (dead-code cleanup, not just a patch). Verified directly against `git show 63eea96`: `openDropdown()` measures via `containerRef.current.querySelector('input').getBoundingClientRect()` on every open, wrapped in try/catch for jsdom/SSR safety. The three remaining bare `setIsOpen(true)` calls (ArrowDown/ArrowUp/typing handlers) are safe as-is — they can only fire on an already-focused input, so `openDropdown()` has always already run via `onFocus` by that point.
- Checkbox "dropped" state uses `.some()` across a group's bindings (any dropped → show as excluded) rather than the plan's `.every()` (all dropped → show as excluded). Reasonable and arguably safer — surfaces a partial-drop state instead of hiding it — but differs from the plan.
- Both of the above were found and verified through direct code review (`git show`, not the implementer's report) after an earlier report for this same task turned out to describe files that didn't exist in the referenced commit. This implementation is real and independently verified: `git diff-tree` confirms the commit touches only `web/` files, `git show` confirms every diff matches what's described above, and both test suites were run fresh (not assumed from a report).

## Tests

`.venv/bin/python -m pytest engine/tests -q` — 402 passed, 0 failed (unchanged from 001gw, correctly — this task touched no `engine/` files).
`cd web && npm test -- --run` — 337 passed, 0 failed. Both verified independently during review.
