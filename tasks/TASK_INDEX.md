# Task Index

## Ready

| Task | Summary |
|---|---|

## Completed

| Task | Summary |
|---|---|
| [002b6-verify-all-orm-models-documented](./completed/002b6-verify-all-orm-models-documented.md) | Verified 31 ORM models: 23 accurate, 4 partial/gap, 3 gaps (FeedSliceRow, ProjectSchemaAnalysis, ChangeRequest/ApprovalRecord underspecified) |
| [002aa-sync-domain-docs-auth](./completed/002aa-sync-domain-docs-auth.md) | Synced auth.md — added session_version, updated AuthSession to JWT+table, fixed 6 session invalidation triggers |
| [002ab-sync-domain-docs-security](./completed/002ab-sync-domain-docs-security.md) | Synced security.md — verified all security boundaries, threat model, control requirements |
| [002ac-sync-domain-docs-management](./completed/002ac-sync-domain-docs-management.md) | Synced management.md — verified session_version, membership model, routes, guards |
| [002ad-sync-domain-docs-governance](./completed/002ad-sync-domain-docs-governance.md) | Synced governance.md — verified 22 invariants, build order, repo map, task workflow |
| [002ae-sync-domain-docs-harness](./completed/002ae-sync-domain-docs-harness.md) | Synced harness.md — noted code restructured to execution/, ai/, mapping/, codegen/, management/ |
| [002af-sync-domain-docs-launch-gate](./completed/002af-sync-domain-docs-launch-gate.md) | Synced launch-gate.md — marked "Domain docs current" as done |
| [002b0-sync-domain-docs-project](./completed/002b0-sync-domain-docs-project.md) | Synced project.md — added project_resources, removed non-existent environment field |
| [002b1-sync-domain-docs-runs](./completed/002b1-sync-domain-docs-runs.md) | Synced runs.md — verified RunRecord, RunCheckpoint, baton sequence, reconciliation |
| [002b2-sync-domain-docs-source-model](./completed/002b2-sync-domain-docs-source-model.md) | Synced source-model.md — applied 002b7 fixes, added FeedSliceRow, ProjectSchemaAnalysis, source_details |
| [002b3-sync-domain-docs-api](./completed/002b3-sync-domain-docs-api.md) | Added Run, Gate, Reconciliation, Impact, Mapping review, Source analysis, New sign-off, Mapping snapshot sections |
| [002b4-sync-domain-docs-ui](./completed/002b4-sync-domain-docs-ui.md) | Synced ui.md — verified operator screens, role views, sign-off review, notifications |
| [002b5-sync-domain-docs-readme](./completed/002b5-sync-domain-docs-readme.md) | Synced README.md — verified all domain docs listed, reading order, spec funnel |
| [002b6-verify-all-orm-models-documented](./completed/002b6-verify-all-orm-models-documented.md) | Verified 31 ORM models: 23 accurate, 4 partial/gap, 3 gaps (FeedSliceRow, ProjectSchemaAnalysis, ChangeRequest/ApprovalRecord) |
| [002b7-fix-mapping-signoff-contradictions](./completed/002b7-document-orm-json-columns.md) | Fixed MappingBindingSignOff (existence-based, no status enum), LookupSignOff (project-scoped, no fiber), deleted stale fiber entities |
| [001gz-reset-codegen-instructions-to-defaults](./completed/001gz-reset-codegen-instructions-to-defaults.md) | Added "Reset to defaults" button to overwrite saved global codegen instructions with merged YAML template. |
| [001gy-fix-reject-mapping-approved-precondition](./completed/001gy-fix-reject-mapping-approved-precondition.md) | [summary](./summary/001gy-fix-reject-mapping-approved-precondition.md) |
| [001gw-table-mapping-drop-toggle-backend](./completed/001gw-table-mapping-drop-toggle-backend.md) | [summary](./summary/001gw-table-mapping-drop-toggle-backend.md) |
| [001gx-table-mapping-drop-toggle-frontend](./completed/001gx-table-mapping-drop-toggle-frontend.md) | [summary](./summary/001gx-table-mapping-drop-toggle-frontend.md) |
| [001gv-react-readonly-input-value-prop-warning](./completed/001gv-react-readonly-input-value-prop-warning.md) | [summary](./summary/001gv-react-readonly-input-value-prop-warning.md) |
| [001gp-codegen-lookup-stacked-verification](./completed/001gp-codegen-lookup-stacked-verification.md) | [summary](./summary/001gp-codegen-lookup-stacked-verification.md) |
| [001go-lookup-review-grid-wiring](./completed/001go-lookup-review-grid-wiring.md) | [summary](./summary/001go-lookup-review-grid-wiring.md) |
| [001gn-lookup-stacked-source-ui](./completed/001gn-lookup-stacked-source-ui.md) | [summary](./summary/001gn-lookup-stacked-source-ui.md) |
| [001gu-lookup-unmapped-source-values-and-case-insensitive-add](./completed/001gu-lookup-unmapped-source-values-and-case-insensitive-add.md) | [summary](./summary/001gu-lookup-unmapped-source-values-and-case-insensitive-add.md) |
| [001gs-lookup-destination-mappings-not-reconciled-from-flat-map](./completed/001gs-lookup-destination-mappings-not-reconciled-from-flat-map.md) | [summary](./summary/001gs-lookup-destination-mappings-not-reconciled-from-flat-map.md) |
| [001gr-lookup-json-mutation-not-detected-bug](./completed/001gr-lookup-json-mutation-not-detected-bug.md) | [summary](./summary/001gr-lookup-json-mutation-not-detected-bug.md) |
| [001gq-lookup-patch-inner-key-casing-bug](./completed/001gq-lookup-patch-inner-key-casing-bug.md) | [summary](./summary/001gq-lookup-patch-inner-key-casing-bug.md) |
| [001fm-lookup-fiber-inputs-upsert-sync](./completed/001fm-lookup-fiber-inputs-upsert-sync.md) | Synchronized `LookupValueMap` (`source_value_map`, `destination_table`, `destination_mappings`) upon AI Analyze input submission and stakeholder fiber approval. Pre-filled textareas in Feed Page. |
| [001fl-destination-label-review-page](./completed/001fl-destination-label-review-page.md) | Widened fallback label extractor in Review Page to extract `destLabel` using 6-key priority search (`label`, `name`, `desc`, etc.). |
| [001fk-destination-labels-empty-in-backend](./completed/001fk-destination-labels-empty-in-backend.md) | Populate `dest_label` in `destination_mappings` groups during auto-creation and PATCH actions (`add_source_value`, `remove_source_value`, `move_source_value`). |
| [001fj-frontend-destination-mappings-ui](./completed/001fj-frontend-destination-mappings-ui.md) | Refactor React frontend components (`LookupMappingTable.tsx`, `review/page.tsx`, `page.tsx`) to directly render `destination_mappings` from the backend API. |
| [001fi-backend-destination-mappings-model](./completed/001fi-backend-destination-mappings-model.md) | [summary](./summary/001fi-backend-destination-mappings-model.md) |
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
