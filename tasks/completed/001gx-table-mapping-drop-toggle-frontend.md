---
id: 001gx
title: Table Mapping "Drop Source Field" as a Soft-Delete Toggle (Frontend) + Autocomplete Dropdown Clip Fix
status: completed
created: 2026-07-25
priority: high
domain: frontend / react / mapping
depends-on: [001gw]
---

# Task 001gx — Table Mapping "Drop Source Field" Toggle (Frontend) + Autocomplete Dropdown Fix

- **Plan**: [2026-07-25-001gx-table-mapping-drop-toggle-frontend.md](../plans/2026-07-25-001gx-table-mapping-drop-toggle-frontend.md)
- **Domain**: [ui.md](../docs/domain/ui.md)

## Context

**Depends on task 001gw** (backend) — this task needs `dropped: bool` present on `field_bindings` in the mapping API response before the toggle UI has anything real to read/write. Do not start this task until 001gw's `MappingFieldBindingResponse.dropped` field exists and `patch_mapping` accepts/persists it.

**Scope note**: this is the *table/field mapping* grid in `ReviewGrid.tsx` (source column → destination column bindings) — not `LookupMappingTable.tsx` (lookup value mappings, covered by 001gq-001gu). Do not touch `LookupMappingTable.tsx`.

Today, the × button (`ReviewGrid.tsx:526-535`) hard-removes a source field's row entirely: `onClick={() => onRemoveSourceField?.(table.destinationTableName, group.sourceField)}`, which in `review/page.tsx`'s `handleRemoveSourceField` (lines 360-386) filters the field out of `fieldBindings` and PATCHes the reduced list — the row just vanishes, with no way to bring it back except manually re-adding the exact same binding.

This task replaces that with a toggle: a checkbox/tick icon in the same position, always visible (read-only when not editable), which flips a `dropped` flag while keeping the row in the table (source field name struck through when dropped). The PATCH now always sends the *full* bindings list with just the target field's flag flipped — this is the contract 001gw's backend assumes for sign-off preservation.

## Requirements

### 1. Toggle UI replaces the × button

`ReviewGrid.tsx`, the field-bindings table (search for `title="Drop this source field from migration"` to find the exact spot):

- Icon renders **always** (not gated by `editingEnabled` — visibility is unconditional per design decision), showing a checked/unchecked state based on whether the source field's bindings are dropped.
- `onClick` is only wired when `editingEnabled` is true (pass `undefined` otherwise, or guard inside the handler) — same interactivity gating as every other edit control in this file, just not the same *visibility* gating the old × button had.
- Source field name (`<span className="font-mono text-slate-700">{group.sourceField}</span>`) gets a strikethrough treatment (`line-through text-slate-400` or similar) when dropped — strikethrough targets the **source** field specifically, per explicit product direction (the model anchors around source, not destination).
- Row stays in the table at all times — dropped is a visual state, not a disappearance.

### 2. Data plumbing: `dropped` threaded end-to-end

Three layers, each currently missing the field:
- `web/lib/mapping-api.ts`: `MappingFieldBindingRecord.dropped`, `MappingSnapshotRaw`'s field_bindings shape, `mapMappingSnapshotResponse`'s mapping, and `patchMappingSnapshot`'s request-building (both the parameter type and the JSON body construction).
- `web/components/projects/ReviewGrid.tsx`: `MappingTableRecord.bindings[].dropped`, and the `groups` construction (search `const groups: Array<{ sourceField: string; bindings: BindingEntry[] }>`) needs a computed `dropped` per group — a group is "dropped" when *all* its bindings are (`group.bindings.every(b => b.dropped)`), since toggling always flips every binding for a source field together (matching the existing all-at-once semantics of the old hard-delete).
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`: the `mappingTablesMap[tblName].bindings.push({...})` construction (search for it) needs to carry `dropped: binding.dropped ?? false` through.

### 3. `handleRemoveSourceField` → `handleToggleSourceField`

Currently filters the field OUT of the bindings array. Must become: map over the *full* current bindings list, and for every binding matching the target `sourceField`, set `dropped` to the new value (don't touch bindings for other source fields) — then PATCH with that full list, not a filtered one. This is the exact contract 001gw's backend sign-off-preservation logic depends on (`patch_mapping`'s `changed_pairs` detection keys on `(source_field, destination_field)` — sending a full list with only a flag changed means no pair is "removed," so sign-offs survive).

### 4. Autocomplete dropdown clip fix (same file, unrelated bug, folded into this task per product request)

`AutocompleteInput` (`ReviewGrid.tsx`, used for the destination-field picker in this same table): its options `<ul>` gets clipped by the table wrapper's `overflow-x-auto` ancestor (CSS spec quirk — `overflow-x: auto` forces `overflow-y` to also compute as clipped, not `visible`, on the same element; z-index cannot escape a clipping ancestor, which is why the existing `z-[100]` doesn't help). Worst for rows near the bottom of the table (the "last item" symptom), since there's no room below to render into.

**Fix** (flip-upward, not a portal — confirmed choice): when opening the dropdown, measure the input's position via `getBoundingClientRect()` against `window.innerHeight`; if there isn't enough room below for the dropdown (`max-h-48` ≈ 192px, budget ~200px), render it above the input instead (`bottom-full mb-1` instead of the current default-flow-below positioning) via a computed `openUpward` boolean state, set at the moment the dropdown opens (not continuously tracked — the row doesn't move while it's open).

## Files to Change

1. `web/lib/mapping-api.ts` — `dropped` field, request/response mapping.
2. `web/components/projects/ReviewGrid.tsx` — toggle UI, `groups` computed `dropped`, `AutocompleteInput` flip-upward fix, prop rename.
3. `web/app/projects/[id]/feeds/[feedId]/review/page.tsx` — `handleRemoveSourceField` → `handleToggleSourceField`, `mappingTablesMap` construction.
4. Test files covering these components (see plan for exact files).

## Verification

```bash
cd web && npm test -- --run
```

Plus manual browser verification (required — no existing test observes CSS clipping or visual strikethrough):
1. On a table with several rows, toggle a source field off. Confirm the row stays visible with the source field name struck through, and the icon shows unchecked.
2. Toggle it back on. Confirm strikethrough clears.
3. As a non-editing viewer (not holding the ball), confirm the icon and strikethrough state are visible but not clickable.
4. Open the destination-field autocomplete on the *last* row of a table with several rows. Confirm the dropdown renders fully visible (opens upward), and every option is selectable — not clipped behind the table's scrollbar.

---
Plan: plans/2026-07-25-001gx-table-mapping-drop-toggle-frontend.md
Summary: tasks/summary/001gx-table-mapping-drop-toggle-frontend.md
