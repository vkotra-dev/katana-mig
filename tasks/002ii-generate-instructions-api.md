---
id: 002ii
title: Server-side transformation spec with source type hints
status: completed
created: 2026-07-27
completed: 2026-07-27
priority: medium
depends-on: [002if]
domain: engine, web
---

# 002ii — "Generate Instructions" API endpoint + client cleanup

## Problem

The "Generate Instructions" button on the codegen page assembles a transformation instructions template client-side in `generateTransformationInstructionsTemplate()` (~115 lines). It lacks `source_type_hint` (e.g., `[integer]`, `[text]`) next to source field names. The backend already has `SourceSchemaArtifact` and `source_type_map` (used by codegen SQL generation flow).

## Solution

### Backend

Add `POST /projects/{project_id}/sources/{source_definition_id}/transformation-spec` that returns a `spec` string with inline type hints.

Response:
```json
{ "spec": "### Transformation Specification for Feed: Customer Extract\n### 1. Approved Lookup Data\n...\n### 2. Approved Destination Mappings\n- Source table: \"stg.customer_extract\"\n- Destination object: \"Customer\"\n  Field bindings:\n  * Source field \"customer_id\" [integer] -> Destination column \"customer_id\"\n...\n### 3. Unmapped Required Destination Fields\n..." }
```

**Steps:**
1. Add schema: `TransformationSpecResponse` in `engine/src/migrations_engine/api/schemas.py`
2. Add endpoint in `engine/src/migrations_engine/routes/codegen.py`
3. Add `generate_transformation_spec()` in `service.py` — reuse SourceSchemaArtifact/source_type_map pattern from codegen flow
4. Add tests in `engine/tests/test_codegen_transformation_spec.py`

### Frontend cleanup

1. **Remove** `generateTransformationInstructionsTemplate()` (~115 lines) from `page.tsx`
2. **Keep** `UnmappedRequiredField` interface and `computeUnmappedRequiredFields()` — used by `toggleExpandFeed` for the expanded-row warning card (independent consumer)
3. **Keep** `feedUnmappedFields` state — used by expanded-row warning card
4. **Update** `handleSuggestFeedInstructions` to call the new API and set textarea value
5. Add `generateTransformationSpec()` to `web/lib/codegen-api.ts`
6. Update frontend test: mock the new API, fix the pre-existing stale `### 5. Source Characteristics` assertion

### Files to modify

**Backend:**
- `engine/src/migrations_engine/api/schemas.py` — add `TransformationSpecResponse`
- `engine/src/migrations_engine/routes/codegen.py` — add `POST /transformation-spec` endpoint
- `engine/src/migrations_engine/codegen/service.py` — add `generate_transformation_spec()`
- `engine/tests/test_codegen_transformation_spec.py` — new test file

**Frontend:**
- `web/lib/codegen-api.ts` — add `generateTransformationSpec()`
- `web/app/projects/[id]/codegen/page.tsx` — remove template function, wire button to API, keep warning card logic intact
- `web/app/projects/[id]/codegen/page.test.tsx` — update test for new API

**Docs:**
- `docs/domain/api.md` — add endpoint documentation

## Test plan

- Backend: new endpoint returns correct spec with type hints from source schema
- Backend: returns 404 for unknown project/source
- Frontend: "Generate Instructions" button calls the API and populates the textarea
- Frontend: type hints (e.g., `[integer]`) appear in the generated text
- Frontend: expanded-row unmapped fields warning card still works (independent code path)
- Frontend: all existing codegen page tests pass (with updated assertions)
