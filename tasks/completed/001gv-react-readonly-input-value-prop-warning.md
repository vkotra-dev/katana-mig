---
id: 001gv
title: Fix React readonly input value/onChange warning in LookupMappingTable
status: completed
created: 2026-07-25
priority: low
domain: frontend / react / cleanup
depends-on: []
---

# Task 001gv — Fix React readonly input `value`/`onChange` warning in LookupMappingTable

## Context

The dev console shows:

```
You provided a `value` prop to a form field without an `onChange` handler.
This will render a read-only field. If the field should be mutable use
`defaultValue`. Otherwise, set either `onChange` or `readOnly`.
```

`LookupMappingTable.tsx:101-106` (the source-value `<input>` inside each destination group row):

```tsx
<input
  type="text"
  readOnly={!editingEnabled}
  value={srcVal}
  className="px-2.5 py-1 text-sm border rounded bg-slate-50 border-slate-200 text-slate-800 focus:outline-none focus:bg-white focus:border-indigo-500 w-full max-w-sm font-mono"
/>
```

**Corrected root cause** (verified against React's actual source, `web/node_modules/react-dom/cjs/react-dom-client.development.js:1414-1427`, function `checkControlledValueProps`): the warning is suppressed when `onChange`, `onInput`, `readOnly`, or `disabled` is truthy. This input has `readOnly={!editingEnabled}` — so the warning is suppressed when `editingEnabled=false` (`readOnly=true`) and **fires when `editingEnabled=true`** (`readOnly=false`, `value` set, no `onChange`/`onInput`/`disabled`). An earlier draft of this task had this backwards (claimed it fires when `editingEnabled=false`); verified precisely against the React source before writing this version.

## Fix — do not use `defaultValue`

A naive fix (unconditionally switching to `defaultValue={srcVal}`) was considered and rejected: it introduces a real display/action-mismatch bug. Each row's `key` is `` `${group.destId}-sv-${idx}` `` — index-based, not content-based. When a source value is removed from the middle of `sourceValues` (e.g. `["A","B","C"]` → `["A","C"]` after removing "B"), React reuses the DOM node at the shifted index (previously "B"'s slot, now holding "C") because the key at that position persists across the reconciliation. `defaultValue` only sets the DOM node's value at mount time — React does not re-sync it on subsequent renders for a reused node. Result: that input would keep displaying the stale "B" while the `×` button right next to it (whose `onClick` closure captures the *current* render's `srcVal`, i.e. "C") would actually delete "C" — a real bug, not just silencing a console warning.

**Correct fix**: this input has no `onChange` anywhere and was never actually editable by direct typing — the only ways `sourceValues` changes are the separate Add (`+ Add another source value`) and Remove (`×`) controls. So it should just always be `readOnly`, matching its real behavior, while staying a controlled input (`value={srcVal}`) so it can never desync from the array when items are added or removed:

```diff
   <input
     type="text"
-    readOnly={!editingEnabled}
+    readOnly
     value={srcVal}
     className="px-2.5 py-1 text-sm border rounded bg-slate-50 border-slate-200 text-slate-800 focus:outline-none focus:bg-white focus:border-indigo-500 w-full max-w-sm font-mono"
   />
```

This satisfies React's warning-suppression condition (`readOnly` truthy) in both `editingEnabled` states, and — unlike the `defaultValue` approach — cannot go stale when items are added or removed from a group's source values.

**Check for CSS side effects before landing this**: the `className` on this input has no `read-only:`-prefixed Tailwind variant classes today (verified by inspection), so making `readOnly` unconditional has no visual side effect. If a future edit adds a `read-only:` variant class to this input, re-check that assumption.

## Files to Change

1. `web/components/projects/LookupMappingTable.tsx` — line ~103, `readOnly={!editingEnabled}` → `readOnly`.

## Verification

```bash
cd web && npm test -- --run
```

Plus manually confirm in the browser dev console: with `editingEnabled=true` (signed in as the role holding the ball, on a draft lookup map), the source-value inputs render with no new console warnings, and removing a middle item from a multi-value destination group still displays the correct remaining values (not stale text) and the `×` button next to each still deletes the value actually shown.

---
Plan: plans/2026-07-25-001gv-react-readonly-input-value-prop-warning.md
Summary: tasks/summary/001gv-react-readonly-input-value-prop-warning.md
