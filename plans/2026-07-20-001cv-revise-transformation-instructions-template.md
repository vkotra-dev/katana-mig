# Revise Transformation Instructions Template — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `generateTransformationInstructionsTemplate` so the user prompt contains only feed-specific mapping data — lookup values, field bindings, row count — and no SQL execution strategy that belongs in the system prompt.

**Architecture:** Single-file frontend change in `web/app/projects/[id]/codegen/page.tsx`. Function signature is unchanged; only the body is replaced. The `strategy` local variable is deleted entirely. No backend, system prompt, or `.j2` template changes.

**Tech Stack:** TypeScript, Next.js (React). No new dependencies.

## Global Constraints

- Edit only `generateTransformationInstructionsTemplate` (lines 145–249).
- Do not touch `generateCodingStandardsTemplate`.
- Do not modify any system-prompt variable or template literal.
- Function signature `(feedLabel, rowCount, fibers, stagingSchema, snapshots): string` must not change.
- Serialization: `JSON.stringify(mapping.sourceValue)`, `JSON.stringify(mapping.destRow)`, `JSON.stringify(mapping.destEntryId ?? null)` — exact forms, no alteration.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `web/app/projects/[id]/codegen/page.tsx` | Modify lines 145–249 | Replace function body; remove `strategy` variable |

---

### Task 1: Replace function body

**Files:**
- Modify: `web/app/projects/[id]/codegen/page.tsx:145-249`

**Interfaces:**
- Consumes: `feedLabel: string`, `rowCount: number`, `fibers: FiberRecord[]`, `stagingSchema: string`, `snapshots: MappingSnapshotRecord[]`
- Produces: `string` — three-section template containing only lookup data, field bindings, source row count

- [ ] **Step 1: Verify what needs to change**

```bash
grep -n "strategy\|Chunked\|Batch Upsert\|row by row\|Create a lookup table\|Execution Strategy\|upsert the mapped" \
  web/app/projects/\[id\]/codegen/page.tsx
```

Expected: lines containing forbidden phrases. If no output, the patch is already applied — confirm with Step 5 and commit.

- [ ] **Step 2: Replace the function body**

In `web/app/projects/[id]/codegen/page.tsx`, replace lines 145–249 with:

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

  const lookupFibers = approvedFibers.filter(
    f => f.fiberType === "lookup"
  );

  const domainFibers = approvedFibers.filter(
    f => f.fiberType === "domain_object"
  );

  let lookupSection = "\n### 1. Approved Lookup Data\n";

  if (lookupFibers.length === 0) {
    lookupSection +=
      "- No approved lookup data was identified for this feed.\n";
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
    mappingSection +=
      "- No approved destination mappings were identified for this feed.\n";
  } else {
    domainFibers.forEach(fiber => {
      const snapshot = snapshots.find(
        snapshot =>
          snapshot.destinationObjectName === fiber.fiberKey
      );

      const bindings =
        snapshot?.fieldBindings ?? fiber.fieldBindings ?? [];

      mappingSection +=
        `\n- Destination object: "${fiber.fiberKey}"\n`;

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

- [ ] **Step 3: Confirm `strategy` is gone**

```bash
grep -n "strategy" web/app/projects/\[id\]/codegen/page.tsx
```

Expected: no output within `generateTransformationInstructionsTemplate`. Any match outside this function is unrelated and must not be changed.

- [ ] **Step 4: Confirm `generateCodingStandardsTemplate` is untouched**

```bash
git diff web/app/projects/\[id\]/codegen/page.tsx | grep "generateCodingStandardsTemplate"
```

Expected: no output.

- [ ] **Step 5: TypeScript check**

```bash
cd web && npx tsc --noEmit
```

Expected: no new type errors. Report any errors without modifying unrelated code.

- [ ] **Step 6: Commit**

```bash
git add "web/app/projects/[id]/codegen/page.tsx"
git commit -m "feat: restrict transformation instructions template to mapping data only (001cv)"
```
