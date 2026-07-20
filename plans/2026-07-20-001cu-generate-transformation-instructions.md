# Generate Transformation Instructions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the body of `generateTransformationInstructionsTemplate` so it emits only feed-specific mapping data (lookup values, field bindings, row count) and drops all SQL execution strategy that belongs in the system prompt.

**Architecture:** Single-file frontend change. The function signature is unchanged — callers are unaffected. No backend changes. The system prompt (global coding standards) already handles SQL strategy; this removes the duplicate user-prompt directives that created conflict.

**Tech Stack:** TypeScript, Next.js (React). No new dependencies.

## Global Constraints

- Do not touch `generateCodingStandardsTemplate`.
- Do not touch any backend file, system prompt template, or `.j2` file.
- Function signature `(feedLabel, rowCount, fibers, stagingSchema, snapshots) => string` must not change.
- `JSON.stringify(mapping.destRow)` stringification must be preserved exactly.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `web/app/projects/[id]/codegen/page.tsx` | Modify lines 145–249 | Replace function body; remove `strategy` variable |

---

### Task 1: Replace `generateTransformationInstructionsTemplate` body

**Files:**
- Modify: `web/app/projects/[id]/codegen/page.tsx:145-249`

**Interfaces:**
- Consumes: `feedLabel: string`, `rowCount: number`, `fibers: FiberRecord[]`, `stagingSchema: string`, `snapshots: MappingSnapshotRecord[]`
- Produces: `string` — multi-section template with lookup data, field bindings, source row count only

**Before (stale implementation that was replaced):**

The old body contained a `strategy` variable that emitted sections titled "Table Mappings & Stored Procedures", "Chunked / Batch Upsert", and "Insert always has to be row by row only and follow the logging strategy" — SQL execution directives that conflict with the system prompt.

**After (target implementation):**

```typescript
const generateTransformationInstructionsTemplate = (
  feedLabel: string,
  rowCount: number,
  fibers: FiberRecord[],
  stagingSchema: string,
  snapshots: MappingSnapshotRecord[]
): string => {
  const approvedFibers = fibers.filter(
    f =>
      f.status === "business_approved" ||
      f.status === "operator_triggered" ||
      f.status === "codegen_complete" ||
      f.status === "active" ||
      f.status === "approved"
  );

  const lookupFibers = approvedFibers.filter(f => f.fiberType === "lookup");
  const domainFibers = approvedFibers.filter(f => f.fiberType === "domain_object");

  let lookupSection = "\n### 1. Approved Lookup Data\n";

  if (lookupFibers.length === 0) {
    lookupSection += "- No approved lookup data was identified for this feed.\n";
  } else {
    lookupFibers.forEach(fiber => {
      lookupSection += `- Approved lookup: "${fiber.fiberKey}"\n`;
      const mappings = fiber.proposedMappings ?? [];
      if (mappings.length === 0) {
        lookupSection += "  Approved mappings: none\n";
        return;
      }
      lookupSection += "  Approved mappings:\n";
      mappings.forEach(mapping => {
        const sourceValue = JSON.stringify(mapping.sourceValue);
        const destinationValue = mapping.destRow
          ? JSON.stringify(mapping.destRow)
          : JSON.stringify(mapping.destEntryId ?? null);
        lookupSection +=
          `    * Source value: ${sourceValue}` +
          ` -> Destination: ${destinationValue}\n`;
      });
    });
  }

  let mappingSection = "\n### 2. Approved Destination Mappings\n";
  mappingSection += `- Source table: "${stagingSchema}.${feedLabel}"\n`;

  if (domainFibers.length === 0) {
    mappingSection += "- No approved destination mappings were identified for this feed.\n";
  } else {
    domainFibers.forEach(fiber => {
      const snapshot = snapshots.find(
        s => s.destinationObjectName === fiber.fiberKey
      );
      const bindings = snapshot?.fieldBindings ?? fiber.fieldBindings ?? [];
      mappingSection += `\n- Destination object: "${fiber.fiberKey}"\n`;
      if (bindings.length === 0) {
        mappingSection += "  Field bindings: none\n";
        return;
      }
      mappingSection += "  Field bindings:\n";
      bindings.forEach(binding => {
        const lookupText = binding.lookupName
          ? ` (Lookup: ${binding.lookupName})`
          : "";
        mappingSection +=
          `    * Source field "${binding.sourceField}"` +
          ` -> Destination column "${binding.destinationField}"` +
          `${lookupText}\n`;
      });
    });
  }

  const sourceCharacteristicsSection =
    "\n### 3. Source Characteristics\n" +
    `- Estimated source row count: ${rowCount}\n`;

  return `### Transformation Specification for Feed: ${feedLabel}
${lookupSection}
${mappingSection}
${sourceCharacteristicsSection}`;
};
```

- [ ] **Step 1: Verify current state matches target**

```bash
grep -n "strategy\|Chunked\|Batch Upsert\|row by row" web/app/projects/\[id\]/codegen/page.tsx
```

Expected: no output — these strings must be absent. If present, apply the implementation above.

- [ ] **Step 2: Confirm `generateCodingStandardsTemplate` is untouched**

```bash
git diff web/app/projects/\[id\]/codegen/page.tsx | grep "generateCodingStandardsTemplate"
```

Expected: no output.

- [ ] **Step 3: TypeScript check**

```bash
cd web && npx tsc --noEmit
```

Expected: no new errors introduced by this change.

- [ ] **Step 4: Commit**

```bash
git add web/app/projects/\[id\]/codegen/page.tsx
git commit -m "feat: restrict codegen instructions template to mapping data only (001cu)"
```

---

## Status

**Implemented.** As of 2026-07-20 the target implementation is in place. `strategy` variable is absent, function body matches the "After" block above, TypeScript compilation passes.