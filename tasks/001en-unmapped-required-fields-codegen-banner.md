---
type: Task Plan
title: Feed-Scoped Banner for Unmapped Required Destination Fields on the Codegen Page
status: ready
---

# Task: 001en-unmapped-required-fields-codegen-banner

## Context

Design spec: `docs/superpowers/specs/2026-07-22-unmapped-required-fields-callout-design.md`
(sections 3, 4, 5).

`001em` (prerequisite, must land first) exposes `MappingSnapshot.destination_columns` through the
mapping API (`MappingSnapshotResponse.destination_columns`, a list of `{name,
destination_data_type, nullable}`), and makes `codegen/service.py` fail loud
(`unmapped_required_destination_fields` / `destination_metadata_missing`) instead of silently
generating code when a required destination field has no source mapping.

That backend fix alone still leaves the operator with only a raw API error and no obvious path to
resolve it. This task adds a visible, feed-scoped warning on the codegen page
(`web/app/projects/[id]/codegen/page.tsx`) so the operator sees which fields are unmapped and can
act — and folds the same information into the existing "Generate Instructions" template so a typed
default value lands directly in `Feed.transformation_instructions`, which is already rendered
verbatim into the codegen AI's prompt (`codegen/templates/user_prompt.txt.j2:13-15`).

## Requirements

1. When a feed's approved `MappingSnapshot` has NOT-NULL destination columns with no matching
   field binding, show a visible warning banner on the codegen page, directly above that feed's
   "Feed-specific transformation instructions" textarea — scoped to that one feed only. Never
   aggregate or mix multiple feeds' unmapped fields into one shared banner.
2. The banner must appear automatically when the feed row is expanded — it must not require the
   operator to first click "Generate Instructions."
3. Extend the existing `generateTransformationInstructionsTemplate` helper with a new
   "Unmapped Required Destination Fields" section, listing each unmapped field with placeholder
   text prompting the operator to specify a default. The operator edits that text in place and
   saves it through the existing "Save" button — no new endpoint, no new stored field.
4. Only a `MappingSnapshot` with `status === "approved"` should ever count toward "unmapped
   required fields" for this feature — a draft snapshot's unmapped fields don't yet block codegen
   (codegen only ever reads the latest *approved* snapshot per
   `codegen/service.py::_select_latest_approved_mapping_snapshot`), so surfacing draft-only issues
   here would be misleading.

## Out of Scope

- No automatic re-trigger of anything after the operator edits the instructions text — they save
  and re-run codegen manually, same as today.
- No structured "default value" storage — the default lives as free text inside
  `transformation_instructions`. If the AI script-generation call doesn't honor it, codegen still
  blocks with the same error as before; there is no second, code-level fallback.
- No changes to `mapping_hints` or the mapping-proposal AI flow.
- No changes to the `MappingReviewGrid`/feed-review page's own separate unmapped-fields warning
  boxes (those already exist from `001dz` and cover a different page).

## Dependencies

Depends on `001em` landing first — this task reads `MappingSnapshotResponse.destination_columns`,
which does not exist in the API until `001em` ships.
