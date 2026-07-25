# Plan: Task 001gv — Fix React readonly input `value`/`onChange` warning in LookupMappingTable

- **Task**: [001gv-react-readonly-input-value-prop-warning.md](file:///Users/vjkotra/projects/katana/tasks/001gv-react-readonly-input-value-prop-warning.md)

---

## Goal Description

`LookupMappingTable.tsx`'s source-value `<input>` has `value={srcVal}` with no `onChange`, and `readOnly={!editingEnabled}` — which only suppresses React's "value without onChange" warning when `editingEnabled=false`. The warning fires when `editingEnabled=true` (verified against React's actual source, not guessed). Fix: make `readOnly` unconditional (`true` always), keep `value={srcVal}` controlled. Do **not** switch to `defaultValue` — that was considered and rejected because it desyncs the displayed text from the array when items are removed from the middle of a multi-value group (index-based `key`s cause DOM node reuse, and `defaultValue` doesn't re-sync on reuse), which would make the `×` button next to a stale-looking value actually delete a different value than what's displayed.

---

## Step 1: Fix the `readOnly` prop

**File**: [web/components/projects/LookupMappingTable.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/LookupMappingTable.tsx)

Search for `readOnly={!editingEnabled}` — it appears exactly once in this file, on the source-value input inside `group.sourceValues.map(...)`:

```diff
                       <input
                         type="text"
-                        readOnly={!editingEnabled}
+                        readOnly
                         value={srcVal}
                         className="px-2.5 py-1 text-sm border rounded bg-slate-50 border-slate-200 text-slate-800 focus:outline-none focus:bg-white focus:border-indigo-500 w-full max-w-sm font-mono"
                       />
```

Do not touch the `value={srcVal}` line, and do not change this to `defaultValue` — see the task doc's "Fix — do not use `defaultValue`" section for why that's rejected.

Do not touch the *other* `<input>` in this same file — the "Enter source value alias..." input used by the inline Add form (`newSourceValue`/`onChange={(e) => setNewSourceValue(e.target.value)}`) is a separate, genuinely controlled+editable input with its own `onChange` and is not affected by this warning at all. Verify with a search that `readOnly={!editingEnabled}` only matches the one location described above before editing.

---

## Step 2: Verify

```bash
cd web && npm test -- --run
```

Expect no change in pass/fail counts versus the commit right before this task — this is a one-line prop change with no behavioral surface for the existing test suite to catch either way (no test in `LookupMappingTable.test.tsx` asserts on the `readOnly` attribute or console warnings today).

**Manual browser verification (do this — it's the only way to actually confirm the fix)**:
1. Start the dev server, open the Review page as the role currently holding the ball on a draft lookup map (`editingEnabled=true`), open the browser dev console.
2. Confirm the "value prop without onChange" warning no longer appears for the lookup mapping table's source-value inputs.
3. Find (or create, via task 001gr/001gs's now-working "+Add another source value") a destination group with 3+ source values. Remove the *middle* one via its `×` button.
4. Confirm the remaining values displayed are correct (not stale — e.g. if you had `["A","B","C"]` and removed "B", the row that's now first-remaining-after-A should show "C", not a leftover "B") and that each `×` button still deletes the value actually printed next to it. This specifically guards against the bug the rejected `defaultValue` approach would have introduced — worth checking even though this task's actual code change (unconditional `readOnly`) doesn't introduce it, just to be sure nothing else in this render path has a similar issue.

---

## Verification Plan

```bash
cd web && npm test -- --run
```

Plus the manual steps in Step 2 — required here specifically because this fix's entire value is "no console warning, and no display/action desync," neither of which any existing automated test observes.
