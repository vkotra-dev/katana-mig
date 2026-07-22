# Plan: 001en — Feed-Scoped Banner for Unmapped Required Destination Fields on the Codegen Page

## Task and Domain links

- Task: `tasks/001en-unmapped-required-fields-codegen-banner.md`
- Design: `docs/superpowers/specs/2026-07-22-unmapped-required-fields-callout-design.md`
- Depends on: `001em` (must be committed and its verification steps all green before starting this
  task — this task reads `MappingSnapshotResponse.destination_columns` / the frontend
  `MappingSnapshotRecord.destinationColumns` field it adds).
- Domain: no `docs/domain/` page currently documents the codegen page's feed-specific instructions
  workflow in enough detail to require an update — no domain doc update required for this task.

## Audience note

This plan is written for an agent with no prior context on this codebase beyond what's quoted
here. Every edit gives the exact current text to find and the exact replacement text. Before
starting, confirm `001em` is actually done: run
`grep -n "destination_columns" engine/src/migrations_engine/api/schemas.py` — it must show a
`destination_columns` field on `MappingSnapshotResponse`. If it doesn't, stop; do not start this
task out of order.

## Current State (verbatim, read immediately before starting)

Before making any edit, re-read each file below in full to confirm it still matches what's quoted
here. If it doesn't match, stop and report the discrepancy instead of guessing.

**`web/lib/mapping-api.ts`** — lines 1-104 (full relevant section, quoted above the split point
where each edit lands):

```typescript
export interface MappingFieldBindingRecord {
  sourceField: string;
  destinationField: string;
  lookupName: string | null;
  bindingType?: "direct" | "detail_fk" | "lookup_fk";
  referenceTableName?: string | null;
  destinationTableName?: string | null;
  destinationDataType?: string | null;
  nullable?: boolean | null;
}

export interface LookupTableReference {
  lookupName: string;
  destinationTableName: string;
}

export interface MappingSnapshotRecord {
  mappingSnapshotId: string;
  projectId: string;
  destinationObjectName: string;
  mappingSnapshotVersion: string;
  fieldBindings: MappingFieldBindingRecord[];
  status: string;
  approvedAt: string | null;
  approvedByUserId: string | null;
  createdAt: string;
  lookupTableReferences: LookupTableReference[];
  destinationFields: string[];

}
```

...

```typescript
type MappingSnapshotRaw = {
  mapping_snapshot_id: string;
  project_id: string;
  destination_object_name: string;
  mapping_snapshot_version: string;
  field_bindings: Array<{
    source_field: string;
    destination_field: string;
    lookup_name: string | null;
    binding_type?: string | null;
    reference_table_name?: string | null;
    destination_table_name?: string | null;
    destination_data_type?: string | null;
    nullable?: boolean | null;
  }>;
  status: string;
  approved_at: string | null;
  approved_by_user_id: string | null;
  created_at: string;
  lookup_table_references?: Array<{
    lookup_name: string;
    destination_table_name: string;
  }>;
  destination_fields?: string[];

};
```

...

```typescript
function mapMappingSnapshotResponse(response: MappingSnapshotRaw): MappingSnapshotRecord {
  return {
    mappingSnapshotId: response.mapping_snapshot_id,
    projectId: response.project_id,
    destinationObjectName: response.destination_object_name,
    mappingSnapshotVersion: response.mapping_snapshot_version,
    fieldBindings: response.field_bindings.map((binding) => ({
      sourceField: binding.source_field,
      destinationField: binding.destination_field,
      lookupName: binding.lookup_name,
      bindingType: binding.binding_type as any,
      referenceTableName: binding.reference_table_name,
      destinationTableName: binding.destination_table_name,
      destinationDataType: binding.destination_data_type,
      nullable: binding.nullable,
    })),
    status: response.status,
    approvedAt: response.approved_at,
    approvedByUserId: response.approved_by_user_id,
    createdAt: response.created_at,
    lookupTableReferences: (response.lookup_table_references ?? []).map((ref) => ({
      lookupName: ref.lookup_name,
      destinationTableName: ref.destination_table_name,
    })),
    destinationFields: response.destination_fields ?? [],

  };
}
```

**`web/app/projects/[id]/codegen/page.tsx`** — relevant excerpts:

Imports (lines 1-18):

```tsx
"use client";

import { use, useEffect, useMemo, useState, Fragment } from "react";
import { Topbar } from "../../../../components/Topbar";
import { ProjectNavigationTabs } from "../../../../components/projects/ProjectNavigationTabs";
import {
  downloadCodegenDeliveryBundle,
  getSchemaAnalysis,
  listCodegenArtifacts,
  triggerSchemaAnalysis,
  triggerCodegen,
  type CodegenArtifactRecord,
  type SchemaAnalysisRecord,
} from "../../../../lib/codegen-api";
import { listFeedContracts, saveTransformationInstructions, listFeedFibers, listFeedSlices, type FeedContractRecord, type FiberRecord } from "../../../../lib/feeds-api";
import { getProject, saveCodegenInstructions, type ProjectRecord } from "../../../../lib/projects-api";
import { getAllApprovedMappingSnapshots, type MappingSnapshotRecord } from "../../../../lib/mapping-api";
import { loadUiSession, type SessionRole, type UiSession } from "../../../../lib/session";
import { AiLogViewer } from "../../../../components/ai-logs/AiLogViewer";
```

`generateTransformationInstructionsTemplate`'s ending (the rest of the function, sections 1-3, is
unchanged — only the part from `sourceCharacteristicsSection` to the final `return` is quoted,
since that's where the edit lands):

```tsx
  const sourceCharacteristicsSection =
    "\n### 3. Source Characteristics\n" +
    `- Estimated source row count: ${rowCount}\n`;

  return `### Transformation Specification for Feed: ${feedLabel}
${lookupSection}
${mappingSection}
${sourceCharacteristicsSection}`;
};
```

`toggleExpandFeed` (lines 461-474):

```tsx
  const toggleExpandFeed = (feedId: string) => {
    if (expandedFeed === feedId) {
      setExpandedFeed(null);
    } else {
      setExpandedFeed(feedId);
      const source = sources.find((s) => s.sourceDefinitionId === feedId);
      if (source && feedInstructions[feedId] === undefined) {
        setFeedInstructions((prev) => ({
          ...prev,
          [feedId]: source.transformationInstructions ?? "",
        }));
      }
    }
  };
```

State declarations near the top of the component (find these two lines — they are not adjacent to
each other in the file, locate each independently):

```tsx
  const [feedInstructions, setFeedInstructions] = useState<Record<string, string>>({});
```

The JSX for the expanded feed row (lines 680-718):

```tsx
                          {expandedFeed === source.sourceDefinitionId && (
                            <tr className="bg-slate-50 border-t border-outline-variant">
                              <td colSpan={5} className="px-8 py-4">
                                <div className="space-y-2">
                                  <h4 className="text-sm font-semibold text-slate-900">
                                    Feed-specific transformation instructions
                                  </h4>
                                  <textarea
                                    className="w-full rounded-lg border border-outline-variant bg-white p-3 text-sm focus:border-primary focus:outline-none disabled:bg-slate-100 disabled:text-slate-500 font-sans"
                                    rows={3}
                                    placeholder="e.g. Map claim_no -> external_claim_number; prepend 'OC' to form a 15-char claim ID."
                                    value={feedInstructions[source.sourceDefinitionId] ?? ""}
                                    onChange={(e) => handleFeedInstructionsChange(source.sourceDefinitionId, e.target.value)}
                                    disabled={role !== "central_team" && role !== "admin"}
                                  />
                                  {(role === "central_team" || role === "admin") && (
                                    <div className="flex justify-end gap-2">
                                      <button
                                        type="button"
                                        className="rounded-lg border border-outline-variant bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
                                        onClick={() => void handleSuggestFeedInstructions(source.sourceDefinitionId, source.label)}
                                        disabled={feedSuggestLoading[source.sourceDefinitionId] || feedSaveLoading[source.sourceDefinitionId]}
                                      >
                                        {feedSuggestLoading[source.sourceDefinitionId] ? "Generating..." : "Generate Instructions"}
                                      </button>
                                      <button
                                        type="button"
                                        className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-hover disabled:bg-slate-200 disabled:text-slate-400"
                                        onClick={() => void handleSaveFeedInstructions(source.sourceDefinitionId)}
                                        disabled={feedSaveLoading[source.sourceDefinitionId] || feedSuggestLoading[source.sourceDefinitionId]}
                                      >
                                        {feedSaveLoading[source.sourceDefinitionId] ? "Saving..." : "Save"}
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
```

## Objective

1. Add `destinationColumns` to the frontend's `MappingSnapshotRecord` type and its JSON mapper.
2. Add a pure helper, `computeUnmappedRequiredFields`, that takes a list of
   `MappingSnapshotRecord` and returns every `{tableName, fieldName}` pair for an
   **approved-status** snapshot where a NOT-NULL destination column has no matching field binding.
3. Fetch each feed's mapping snapshots and compute this list the moment its row is expanded (not
   only when "Generate Instructions" is clicked), and store it per-feed.
4. Render a warning banner above the "Feed-specific transformation instructions" textarea when that
   feed has a non-empty list.
5. Extend `generateTransformationInstructionsTemplate`'s output with a new section built from the
   same helper.

## File Changes

### 1. `web/lib/mapping-api.ts`

**1a.** Find this exact interface (quoted in full above under Current State):

```typescript
export interface MappingFieldBindingRecord {
  sourceField: string;
  destinationField: string;
  lookupName: string | null;
  bindingType?: "direct" | "detail_fk" | "lookup_fk";
  referenceTableName?: string | null;
  destinationTableName?: string | null;
  destinationDataType?: string | null;
  nullable?: boolean | null;
}
```

Immediately after it (before `export interface LookupTableReference`), insert a new interface:

```typescript
export interface MappingDestinationColumnRecord {
  name: string;
  destinationDataType?: string | null;
  nullable?: boolean | null;
}
```

**1b.** Find this exact block inside `MappingSnapshotRecord` (quoted in full above):

```typescript
  lookupTableReferences: LookupTableReference[];
  destinationFields: string[];

}
```

Replace with:

```typescript
  lookupTableReferences: LookupTableReference[];
  destinationFields: string[];
  destinationColumns: MappingDestinationColumnRecord[];

}
```

**1c.** Find this exact block inside `MappingSnapshotRaw` (quoted in full above):

```typescript
  lookup_table_references?: Array<{
    lookup_name: string;
    destination_table_name: string;
  }>;
  destination_fields?: string[];

};
```

Replace with:

```typescript
  lookup_table_references?: Array<{
    lookup_name: string;
    destination_table_name: string;
  }>;
  destination_fields?: string[];
  destination_columns?: Array<{
    name: string;
    destination_data_type?: string | null;
    nullable?: boolean | null;
  }> | null;

};
```

**1d.** Find this exact block inside `mapMappingSnapshotResponse` (quoted in full above):

```typescript
    lookupTableReferences: (response.lookup_table_references ?? []).map((ref) => ({
      lookupName: ref.lookup_name,
      destinationTableName: ref.destination_table_name,
    })),
    destinationFields: response.destination_fields ?? [],

  };
```

Replace with:

```typescript
    lookupTableReferences: (response.lookup_table_references ?? []).map((ref) => ({
      lookupName: ref.lookup_name,
      destinationTableName: ref.destination_table_name,
    })),
    destinationFields: response.destination_fields ?? [],
    destinationColumns: (response.destination_columns ?? []).map((c) => ({
      name: c.name,
      destinationDataType: c.destination_data_type,
      nullable: c.nullable,
    })),

  };
```

### 2. `web/app/projects/[id]/codegen/page.tsx`

**2a.** Add a new pure helper function. Place it directly above
`generateTransformationInstructionsTemplate` (find the exact line
`const generateTransformationInstructionsTemplate = (` and insert this immediately before it, with
a blank line separating the two):

```tsx
function computeUnmappedRequiredFields(
  snapshots: MappingSnapshotRecord[]
): { tableName: string; fieldName: string }[] {
  const result: { tableName: string; fieldName: string }[] = [];
  snapshots
    .filter((s) => s.status === "approved")
    .forEach((snapshot) => {
      const boundDestFields = new Set(
        (snapshot.fieldBindings || []).map((b) => b.destinationField)
      );
      (snapshot.destinationColumns || []).forEach((col) => {
        if (col.nullable === false && !boundDestFields.has(col.name)) {
          result.push({ tableName: snapshot.destinationObjectName, fieldName: col.name });
        }
      });
    });
  return result;
}

```

**2b.** Find this exact block at the end of `generateTransformationInstructionsTemplate` (quoted in
full above under Current State):

```tsx
  const sourceCharacteristicsSection =
    "\n### 3. Source Characteristics\n" +
    `- Estimated source row count: ${rowCount}\n`;

  return `### Transformation Specification for Feed: ${feedLabel}
${lookupSection}
${mappingSection}
${sourceCharacteristicsSection}`;
};
```

Replace with:

```tsx
  const sourceCharacteristicsSection =
    "\n### 3. Source Characteristics\n" +
    `- Estimated source row count: ${rowCount}\n`;

  const unmappedRequiredFields = computeUnmappedRequiredFields(snapshots);
  let unmappedRequiredSection = "";
  if (unmappedRequiredFields.length > 0) {
    unmappedRequiredSection = "\n### 4. Unmapped Required Destination Fields\n";
    unmappedRequiredFields.forEach((f) => {
      unmappedRequiredSection += `- "${f.tableName}.${f.fieldName}" is NOT NULL with no source mapping. Specify a default value or expression for the generated SQL to use.\n`;
    });
  }

  return `### Transformation Specification for Feed: ${feedLabel}
${lookupSection}
${mappingSection}
${sourceCharacteristicsSection}${unmappedRequiredSection}`;
};
```

**2c.** Find this exact state declaration:

```tsx
  const [feedInstructions, setFeedInstructions] = useState<Record<string, string>>({});
```

Immediately after it (same line style, same section of state declarations), insert:

```tsx
  const [unmappedRequiredFields, setUnmappedRequiredFields] = useState<Record<string, { tableName: string; fieldName: string }[]>>({});
```

**2d.** Find this exact function (quoted in full above under Current State):

```tsx
  const toggleExpandFeed = (feedId: string) => {
    if (expandedFeed === feedId) {
      setExpandedFeed(null);
    } else {
      setExpandedFeed(feedId);
      const source = sources.find((s) => s.sourceDefinitionId === feedId);
      if (source && feedInstructions[feedId] === undefined) {
        setFeedInstructions((prev) => ({
          ...prev,
          [feedId]: source.transformationInstructions ?? "",
        }));
      }
    }
  };
```

Replace with:

```tsx
  const toggleExpandFeed = (feedId: string) => {
    if (expandedFeed === feedId) {
      setExpandedFeed(null);
    } else {
      setExpandedFeed(feedId);
      const source = sources.find((s) => s.sourceDefinitionId === feedId);
      if (source && feedInstructions[feedId] === undefined) {
        setFeedInstructions((prev) => ({
          ...prev,
          [feedId]: source.transformationInstructions ?? "",
        }));
      }
      if (session && routeParams && unmappedRequiredFields[feedId] === undefined) {
        void getAllApprovedMappingSnapshots(session.accessToken, routeParams.id, feedId, true)
          .then((snapshots) => {
            setUnmappedRequiredFields((prev) => ({
              ...prev,
              [feedId]: computeUnmappedRequiredFields(snapshots),
            }));
          })
          .catch(() => {
            setUnmappedRequiredFields((prev) => ({ ...prev, [feedId]: [] }));
          });
      }
    }
  };
```

**2e.** Find this exact JSX block (quoted in full above under Current State — only the opening
`<div className="space-y-2">` through the `<h4>` line matter for locating the insertion point;
everything else in the block is unchanged):

```tsx
                                <div className="space-y-2">
                                  <h4 className="text-sm font-semibold text-slate-900">
                                    Feed-specific transformation instructions
                                  </h4>
```

Replace with:

```tsx
                                <div className="space-y-2">
                                  {(unmappedRequiredFields[source.sourceDefinitionId]?.length ?? 0) > 0 && (
                                    <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                                      <p className="font-semibold">
                                        {unmappedRequiredFields[source.sourceDefinitionId].length} required destination field
                                        {unmappedRequiredFields[source.sourceDefinitionId].length > 1 ? "s are" : " is"} unmapped — code generation will fail until resolved.
                                      </p>
                                      <ul className="mt-1 list-disc pl-4">
                                        {unmappedRequiredFields[source.sourceDefinitionId].map((f, idx) => (
                                          <li key={idx} className="font-mono">{f.tableName}.{f.fieldName}</li>
                                        ))}
                                      </ul>
                                      <p className="mt-1">Add a default value or expression for these fields in the instructions below, or click "Generate Instructions" to include them automatically.</p>
                                    </div>
                                  )}
                                  <h4 className="text-sm font-semibold text-slate-900">
                                    Feed-specific transformation instructions
                                  </h4>
```

## Tests

Add these to `web/app/projects/[id]/codegen/page.test.tsx`. Read the existing test
`"generates feed-specific transformation instructions"` (lines 322-344 as of this writing) first —
match its structure (render, expand the row via the `▶` toggle, `findByRole`/`findByText`,
`waitFor`) exactly.

1. **Extend the existing mock snapshot fixture.** The `beforeEach` block's
   `getAllApprovedMappingSnapshotsMock.mockResolvedValue([...])` (around line 201) currently seeds
   one snapshot for `"customer"` with a single bound field and no `destinationColumns`. Add
   `destinationColumns: [{ name: "customer_id", destinationDataType: "INT", nullable: false }]` to
   that existing mock object (this field is fully mapped already — this alone should NOT trigger
   the banner; it's the baseline "no unmapped fields" case other tests build on).
2. **New test: `"shows an unmapped required fields banner when a NOT-NULL column has no
   binding"`.** In this test, override the mock with
   `getAllApprovedMappingSnapshotsMock.mockResolvedValueOnce([...])` (or `mockResolvedValue`, see
   how other tests in this file override per-test — check `mockResolvedValueOnce` usage around
   lines 248 and 263 for the pattern) supplying a snapshot with `destinationColumns` containing one
   NOT-NULL column with no matching entry in `fieldBindings` (e.g. add
   `{ name: "account_status", destinationDataType: "VARCHAR(20)", nullable: false }` to
   `destinationColumns` without a matching binding). Render the page, expand the feed row (click
   the `▶` toggle), and assert the banner text appears (e.g.
   `await screen.findByText(/customer.account_status/)` or match on the exact rendered text —
   confirm the precise DOM text by reading the JSX inserted in step 2e above).
3. **New test: `"does not show a banner when all required fields are mapped"`.** Uses the
   baseline fixture from step 1 (no unmapped fields). Render, expand the row, and assert
   `screen.queryByRole("alert")` is `null` (or query for the specific banner text and assert it's
   absent) — confirms the banner doesn't render unconditionally.
4. **Extend the existing test `"generates feed-specific transformation instructions"`** (or add a
   new one alongside it) with an unmapped-required-field snapshot in the mock, click "Generate
   Instructions", and assert the resulting textarea value contains
   `"### 4. Unmapped Required Destination Fields"` and the specific field name.

## Verification

Run these from the repo root (`/Users/vjkotra/projects/katana`) in order — all must pass:

```bash
cd web && npx tsc --noEmit
```
Expect: no new type errors. This catches any interface mismatch introduced by the
`MappingSnapshotRecord`/`MappingSnapshotRaw` edits before running any test.

```bash
cd web && npx vitest run "app/projects/[id]/codegen/page.test.tsx"
```
Expect: all tests pass, including the pre-existing 8 tests in this file (do not break
`"generates feed-specific transformation instructions"` or any other existing test — if any
existing test starts failing, that's a signal an edit above was applied to the wrong location or
introduced an unintended change) plus the new tests added in this task.

```bash
cd web && npx vitest run
```
Expect: full frontend suite passes, same pass count as before this task plus the new tests.

## Pitfalls

- **`computeUnmappedRequiredFields` must filter to `status === "approved"` internally**, not rely
  on the caller to only pass approved snapshots. Both call sites in this task
  (`toggleExpandFeed`'s fetch and `generateTransformationInstructionsTemplate`) pass
  `anyStatus=true`/an unfiltered snapshot list — the helper's own `.filter((s) => s.status ===
  "approved")` is what keeps a draft snapshot's unmapped fields from incorrectly triggering the
  banner or template section. Do not remove or weaken this filter.
- **Do not duplicate the unmapped-fields computation logic.** Both the banner (2d) and the template
  section (2b) must call the same `computeUnmappedRequiredFields` helper — do not write a second,
  slightly different inline version in either place. This codebase has hit real bugs from
  duplicated parsing/validation logic drifting apart (see `001ek`'s history of two independent DDL
  parsers with the same latent bug) — one helper, two call sites.
- **The banner must be feed-scoped.** `unmappedRequiredFields` is keyed by `feedId` — never
  render a combined list across feeds, and never let one feed's fetch overwrite another's key in
  state (the `setUnmappedRequiredFields((prev) => ({ ...prev, [feedId]: ... }))` spread pattern
  above is what keeps each feed's entry independent — do not simplify it to a flat non-keyed
  array).
- **`toggleExpandFeed`'s existing behavior must be preserved exactly** when collapsing a row
  (`expandedFeed === feedId` branch) — the new fetch logic only runs in the `else` branch, same as
  the existing `feedInstructions` fetch it sits next to. Do not fetch snapshots when collapsing.
- **Guard against re-fetching on every expand/collapse toggle.** The `unmappedRequiredFields[feedId]
  === undefined` check (mirroring the existing `feedInstructions[feedId] === undefined` check
  immediately above it) is what makes this a fetch-once-per-feed-per-page-load pattern, not a
  fetch-on-every-click pattern. Keep that guard.
- **This task cannot start before `001em` is done.** `MappingSnapshotRecord.destinationColumns`
  does not exist until `001em`'s frontend-facing API change ships; starting this task early means
  building against a field that doesn't exist yet.

## Commit

Own commit, after `001em` is committed. Suggested message: `feat: warn about unmapped required
destination fields on the codegen page (001en)`.
