# Task Index

## Ready

| Task | Summary |
|---|---|
| [001fi-backend-destination-mappings-model](./001fi-backend-destination-mappings-model.md) | Refactor `LookupValueMap` and `LookupSnapshot` backend DB models, API schemas, and routes to natively store and manage 1-to-Many Destination-Anchored mappings (`destination_mappings: list[dict]`). Add backend PATCH actions for adding/removing source values per destination. |
| [001fj-frontend-destination-mappings-ui](./001fj-frontend-destination-mappings-ui.md) | Refactor React frontend components (`LookupMappingTable.tsx`, `review/page.tsx`, `page.tsx`) to directly render `destination_mappings` from the backend API, removing client-side data inversions. Wire inline `+ Add source` and `×` delete buttons to backend PATCH API actions. |


## Completed

| Task | Summary |
|---|---|
| [001fd-codegen-lookup-integration](./completed/001fd-codegen-lookup-integration.md) | [summary](./summary/001fd-codegen-lookup-integration.md) |
| [001fh-prune-transient-lookup-tables](./completed/001fh-prune-transient-lookup-tables.md) | [summary](./summary/001fh-prune-transient-lookup-tables.md) |
| [001fg-refactor-lookup-fiber-to-json](./completed/001fg-refactor-lookup-fiber-to-json.md) | [summary](./summary/001fg-refactor-lookup-fiber-to-json.md) |
| [001fe-review-page-lookup-grid-display](./completed/001fe-review-page-lookup-grid-display.md) | [summary](./summary/001fe-review-page-lookup-grid-display.md) |
| [001fc-lookup-fiber-prompt-and-review-edit](./completed/001fc-lookup-fiber-prompt-and-review-edit.md) | [summary](./summary/001fc-lookup-fiber-prompt-and-review-edit.md) |
| [001ey-explicit-json-schema-in-lookup-mapping-prompt](./completed/001ey-explicit-json-schema-in-lookup-mapping-prompt.md) | Updated `lookup_mapping.yaml` to explicitly define the output JSON schema contract, preventing local LLM hallucinations. |
| [001ex-unmapped-lookup-row-counts](./completed/001ex-unmapped-lookup-row-counts.md) | Added `data_profile` to `FeedSlice` and computed `unmapped_row_count` dynamically for LookupValueMap API responses. Displayed warnings in Feed and Review pages. All 77 tests pass. |
| [001ew-review-page-lookup-virtualization-and-editing](./completed/001ew-review-page-lookup-virtualization-and-editing.md) | Enabled manual editing and IntersectionObserver-based virtualized scrolling for massive lookup tables on the Review page. Added backend PATCH route for updating lookup mappings. Verified 31/31 tests pass (9 backend, 22 frontend). |
| [001ev-codegen-logging-prompt-extraction](./completed/001ev-codegen-logging-prompt-extraction.md) | Extracted rules 17–21 (mig_upsert_log audit logging instructions) from each platform block in `codegen_coding_standards.yaml` into new `codegen_logging_standards.yaml`. Renderer updated to load and append both with same `$stg/$dest` substitutions. 6 new tests (17/17). 364/364 full suite. |
| [001es-wire-suggest-standards-button-to-backend-endpoint](./completed/001es-wire-suggest-standards-button-to-backend-endpoint.md) | Wired the "Suggest Standards" button to the new codegen-coding-standards-template endpoint; deleted the old local generateCodingStandardsTemplate function (~100 lines). No behavior change. Verified: 311/311 frontend tests pass. |
| [001eu-engine-aware-mig-upsert-log-ddl](./completed/001eu-engine-aware-mig-upsert-log-ddl.md) | `_mig_upsert_log_ddl`/`_assemble_sql_bundle` used to hardcode MSSQL-only DDL and inject it into every generated bundle regardless of target_db_engine. Now engine-aware (mssql/postgresql/mysql/oracle), defaults to mssql when unset for backward compat. Verified: 358/358 backend tests pass. |
