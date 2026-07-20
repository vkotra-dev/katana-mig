# Fix 001cv Code Review Findings — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4 actionable findings from the 001cv code review: stale tests, destEntryId quoting, missing stagingSchema guard, and snapshot variable shadow.

**Architecture:** All changes are in one frontend file (`page.tsx`) and its test (`page.test.tsx`). No backend, API, or system-prompt changes. No new dependencies.

**Tech Stack:** TypeScript, Next.js (React), Vitest/Jest.

## Global Constraints

- Do not change `generateCodingStandardsTemplate` or any system-prompt variable.
- Function signature of `generateTransformationInstructionsTemplate` must not change.
- Serialization of `destRow` via `JSON.stringify(mapping.destRow)` must be preserved exactly.
- All test assertions must pass after the changes.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `web/app/projects/[id]/codegen/page.tsx` | Modify lines 192, 203, 210–211 | Fix destEntryId encoding, add stagingSchema guard, rename shadow variable |
| `web/app/projects/[id]/codegen/page.test.tsx` | Modify lines 335–342 | Update stale assertions to match new output format |

---

### Task 1: Fix stagingSchema guard and snapshot variable shadow

**Files:**
- Modify: `web/app/projects/[id]/codegen/page.tsx`

**Interfaces:**
- `stagingSchema: string` parameter — may be empty string if caller omits the `|| "staging"` guard
- `snapshots: MappingSnapshotRecord[]` — array of approved snapshots, `destinationObjectName` is the match key

- [ ] **Step 1: Add internal stagingSchema guard**

In `web/app/projects/[id]/codegen/page.tsx`, inside `generateTransformationInstructionsTemplate`, add a guard immediately after the `domainFibers` filter (before the `lookupSection` initialization). Replace the raw `stagingSchema` usage at line 203 with `schema`.

Find:
```typescript
  const domainFibers = approvedFibers.filter(
    f => f.fiberType === "domain_object"
  );

  let lookupSection = "\n### 1. Approved Lookup Data\n";
```

Replace with:
```typescript
  const domainFibers = approvedFibers.filter(
    f => f.fiberType === "domain_object"
  );

  const schema = stagingSchema || "staging";

  let lookupSection = "\n### 1. Approved Lookup Data\n";
```

Then update line 203:

Find:
```typescript
  mappingSection += `- Source table: "${stagingSchema}.${feedLabel}"\n`;
```

Replace with:
```typescript
  mappingSection += `- Source table: "${schema}.${feedLabel}"\n`;
```

- [ ] **Step 2: Rename snapshot shadow in find callback**

Find:
```typescript
      const snapshot = snapshots.find(
        snapshot =>
          snapshot.destinationObjectName === fiber.fiberKey
      );
```

Replace with:
```typescript
      const snapshot = snapshots.find(
        snap =>
          snap.destinationObjectName === fiber.fiberKey
      );
```

- [ ] **Step 3: Verify no TypeScript errors**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: no output (or output unchanged from baseline — no new errors).

- [ ] **Step 4: Commit**

```bash
git add "web/app/projects/[id]/codegen/page.tsx"
git commit -m "fix: add stagingSchema guard and rename snapshot shadow variable (001cw)"
```

---

### Task 2: Fix destEntryId encoding and update stale tests

**Files:**
- Modify: `web/app/projects/[id]/codegen/page.tsx` — line 192
- Modify: `web/app/projects/[id]/codegen/page.test.tsx` — lines 335–342

**Context on destEntryId encoding decision:**

The old code emitted `destEntryId` as a bare string (`entry-1`) when non-null. The new code wraps it in `JSON.stringify` which adds surrounding quotes (`"entry-1"`). For an AI prompt generating SQL stored procedures, the bare form is preferable — a quoted ID looks like a string literal to hardcode rather than a lookup key. Revert `destEntryId` encoding to the bare form while keeping the `null` fallback as `"null"` (JSON-style, consistent with the rest of the new prompt).

**Target encoding table:**

| Condition | Old output | New (target) output |
|---|---|---|
| `destRow` is non-null | `JSON.stringify(destRow)` | `JSON.stringify(destRow)` (unchanged) |
| `destRow` null, `destEntryId` non-null string | `entry-1` (bare) | `entry-1` (bare — revert) |
| `destRow` null, `destEntryId` null | `NULL` | `null` (intentional change, keep) |

- [ ] **Step 1: Fix destEntryId encoding**

In `web/app/projects/[id]/codegen/page.tsx`, find:

```typescript
        const destinationValue = mapping.destRow
          ? JSON.stringify(mapping.destRow)
          : JSON.stringify(mapping.destEntryId ?? null);
```

Replace with:

```typescript
        const destinationValue = mapping.destRow
          ? JSON.stringify(mapping.destRow)
          : (mapping.destEntryId ?? "null");
```

- [ ] **Step 2: Run the existing tests to see which assertions fail**

```bash
cd web && npx vitest run app/projects/\\[id\\]/codegen/page.test.tsx 2>&1 | tail -40
```

Expected: test "generates feed-specific transformation instructions" fails with assertions about old strings. Note which assertions fail.

- [ ] **Step 3: Update stale test assertions**

In `web/app/projects/[id]/codegen/page.test.tsx`, find the `waitFor` block for the "generates feed-specific transformation instructions" test (around line 333):

```typescript
    await waitFor(() => {
      expect(textarea.value).toContain("Transformation Instructions for Feed:");
      expect(textarea.value).toContain("insurance_plan_lkp");
      expect(textarea.value).toContain("Gold Plan");
      expect(textarea.value).toContain("source as first column and destination columns as other fields");
      expect(textarea.value).toContain('find the id values from "insurance_plan_lkp" for insert');
      expect(textarea.value).toContain('Look for a table in the source schema with the same name as the feed ("Customer extract") and upsert the mapped source fields into the target destination table(s) using the stakeholder-approved field mappings described below:');
      expect(textarea.value).toContain('Table Mapping Fiber: "customer" (Source: "Customer extract" -> Destination: "customer")');
      expect(textarea.value).toContain('Source field "cust_id" -> Destination column "customer_id"');
    });
```

Replace with assertions matching the new output format:

```typescript
    await waitFor(() => {
      expect(textarea.value).toContain("Transformation Specification for Feed:");
      expect(textarea.value).toContain("### 1. Approved Lookup Data");
      expect(textarea.value).toContain('- Approved lookup: "insurance_plan_lkp"');
      expect(textarea.value).toContain('"Gold Plan"');
      expect(textarea.value).toContain("### 2. Approved Destination Mappings");
      expect(textarea.value).toContain('- Destination object: "customer"');
      expect(textarea.value).toContain('Source field "cust_id" -> Destination column "customer_id"');
      expect(textarea.value).toContain("### 3. Source Characteristics");
    });
```

- [ ] **Step 4: Run the test again to confirm it passes**

```bash
cd web && npx vitest run app/projects/\\[id\\]/codegen/page.test.tsx 2>&1 | tail -20
```

Expected: all tests pass. If any assertion fails, read the actual `textarea.value` from the failure output and adjust the assertion to match the real string produced.

- [ ] **Step 5: TypeScript check**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors.

- [ ] **Step 6: Commit**

```bash
git add "web/app/projects/[id]/codegen/page.tsx" "web/app/projects/[id]/codegen/page.test.tsx"
git commit -m "fix: revert destEntryId to bare string encoding and update stale tests (001cw)"
```
