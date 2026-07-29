# Summary: 002ii — Server-side transformation spec with source type hints

## Goal

Replace the client-side ~115-line template assembly in `generateTransformationInstructionsTemplate()` with a single backend API call that returns a pre-built transformation spec with inline type hints (e.g., `[integer]`, `[text]`).

## What was shipped

**Backend:**
- `POST /projects/{project_id}/sources/{source_definition_id}/transformation-spec` endpoint in `routes/codegen.py`
- `TransformationSpecResponse` schema in `api/schemas.py`
- `generate_transformation_spec()` in `codegen/service.py` — queries approved fibers, fetches SourceSchemaArtifact for type hints, augments field bindings with inline type hints, computes unmapped required fields
- Fiber fallback: when no MappingSnapshot exists, uses `fiber.field_bindings`

**Frontend:**
- `generateTransformationSpec()` in `lib/codegen-api.ts`
- Removed `generateTransformationInstructionsTemplate()` (~115 lines) from `page.tsx`
- Removed `UnmappedRequiredField` interface and `computeUnmappedRequiredFields()` (logic inlined in `toggleExpandFeed` for the warning card)
- `handleSuggestFeedInstructions` now calls the new API
- Frontend test updated: mock API, removed stale `### 5. Source Characteristics` assertion

**Tests:**
- 6 new backend tests in `test_codegen_transformation_spec.py`

## Verification

- Backend: 468 passed (unchanged)
- Frontend: 8/9 tests pass in `page.test.tsx` (1 pre-existing failure: "Suggest Standards" button doesn't exist)
- feedUnmappedFields warning card logic preserved and functional
