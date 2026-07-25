---
id: 001gv
title: Fix React readonly input value/onChange warning in LookupMappingTable
status: active
created: 2026-07-25
priority: low
domain: frontend / react / cleanup
depends-on: []
---

# Task 001gv — Fix React readonly input `value`/`onChange` warning in LookupMappingTable

## Context

The dev server console shows:

```
You provided a `value` prop to a form field without an `onChange` handler.
This will render a read-only field. If the field should be mutable use
`defaultValue`. Otherwise, set either `onChange` or `readOnly`.
```

This occurs in `LookupMappingTable.tsx` line 104 where the source-value `<input>` uses `value={srcVal}` together with `readOnly={!editingEnabled}`. When `editingEnabled` is `false`, React sees a controlled `value` prop on an input that has no `onChange` — even though the input is `readOnly`. This is a known React behavior: a `value` prop without `onChange` is treated as a potential bug (the user might expect to type but can't because `value` resets).

## Fix

**File**: `web/components/projects/LookupMappingTable.tsx`, lines 101-106

Replace the single `value` prop with a conditional using `defaultValue`:

```tsx
<input
  type="text"
  readOnly={!editingEnabled}
  value={!editingEnabled ? undefined : srcVal}
  className="..."
/>
```

Or equivalently (cleaner):

```tsx
<input
  type="text"
  readOnly={!editingEnabled}
  defaultValue={editingEnabled ? srcVal : undefined}
  className="..."
/>
```

When `editingEnabled` is `false`, the input renders as a fully controlled read-only field via `readOnly` + `defaultValue` without the React warning. When `editingEnabled` is `true`, it renders normally with the `value` prop (which works because the `onChange` handler is provided by the parent `onChange` prop pattern).

**Note**: Actually the input has no `onChange` handler at all — it's a plain text input where the user can type when not read-only. So the correct fix is to use `defaultValue` unconditionally and let the input be uncontrolled:

```tsx
<input
  type="text"
  readOnly={!editingEnabled}
  defaultValue={srcVal}
  className="..."
/>
```

This removes the `value` prop entirely, which is correct because:
1. When `editingEnabled=false`, the input is `readOnly` — it's displayed, not edited
2. When `editingEnabled=true`, the user can type, and the parent `onRemoveSourceValue`/`onAddSourceValue` handlers don't actually listen to input changes (they only fire on button clicks for the inline add form). The `srcVal` is displayed but not actively bound to parent state.

## Verification

```bash
cd web && npm test -- --run
```

Plus visually confirm in the browser that:
- Source values display correctly in both readonly and edit modes
- No new console warnings appear
