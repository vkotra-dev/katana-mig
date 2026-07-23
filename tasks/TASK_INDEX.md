# Task Index

## Ready

| Task | Summary |
|---|---|


## Completed

| Task | Summary |
|---|---|
| [001ey-explicit-json-schema-in-lookup-mapping-prompt](./completed/001ey-explicit-json-schema-in-lookup-mapping-prompt.md) | Updated `lookup_mapping.yaml` to explicitly define the output JSON schema contract, preventing local LLM hallucinations. |
| [001ex-unmapped-lookup-row-counts](./completed/001ex-unmapped-lookup-row-counts.md) | Added `data_profile` to `FeedSlice` and computed `unmapped_row_count` dynamically for LookupValueMap API responses. Displayed warnings in Feed and Review pages. All 77 tests pass. |
| [001ew-review-page-lookup-virtualization-and-editing](./completed/001ew-review-page-lookup-virtualization-and-editing.md) | Enabled manual editing and IntersectionObserver-based virtualized scrolling for massive lookup tables on the Review page. Added backend PATCH route for updating lookup mappings. Verified 31/31 tests pass (9 backend, 22 frontend). |
| [001ev-codegen-logging-prompt-extraction](./completed/001ev-codegen-logging-prompt-extraction.md) | Extracted rules 17–21 (mig_upsert_log audit logging instructions) from each platform block in `codegen_coding_standards.yaml` into new `codegen_logging_standards.yaml`. Renderer updated to load and append both with same `$stg/$dest` substitutions. 6 new tests (17/17). 364/364 full suite. |
| [001es-wire-suggest-standards-button-to-backend-endpoint](./completed/001es-wire-suggest-standards-button-to-backend-endpoint.md) | Wired the "Suggest Standards" button to the new codegen-coding-standards-template endpoint; deleted the old local generateCodingStandardsTemplate function (~100 lines). No behavior change. Verified: 311/311 frontend tests pass. |
| [001eu-engine-aware-mig-upsert-log-ddl](./completed/001eu-engine-aware-mig-upsert-log-ddl.md) | `_mig_upsert_log_ddl`/`_assemble_sql_bundle` used to hardcode MSSQL-only DDL and inject it into every generated bundle regardless of target_db_engine. Now engine-aware (mssql/postgresql/mysql/oracle), defaults to mssql when unset for backward compat. Verified: 358/358 backend tests pass. |

| Task | Summary |
|---|---|
| [001et-audit-strategy-per-engine-coding-standards](./completed/001et-audit-strategy-per-engine-coding-standards.md) | Fixed hardcoded oc_stag/cxp schema names in mssql coding standards (now $stg/$dest merge fields); added full parallel-depth "Migration SP Requirements" audit-trace content to postgresql/mysql/oracle sections; fixed a real loader bug (engine-specific block was never merge-field-substituted); removed the redundant, MSSQL-only hardcoded "RUN LOGGING REQUIREMENTS" append from codegen/service.py. Verified: 353/353 backend tests pass. |
| [001er-extract-codegen-coding-standards-backend](./completed/001er-extract-codegen-coding-standards-backend.md) | Exposed the codegen coding-standards template via a new backend YAML file + endpoint. Prerequisite for 001es and 001et. |
| [001eq-review-page-stacked-destination-cell-with-delete](./completed/001eq-review-page-stacked-destination-cell-with-delete.md) | Review page: group bindings by source field into one row, stack destination fields in one cell with per-entry delete (hidden on first entry) plus a whole-source-field delete. Depended on 001ep. Verified: 311/311 frontend tests pass. |
| [001eo-autocomplete-lov-show-all-on-open](./completed/001eo-autocomplete-lov-show-all-on-open.md) | Review page: destination-field picker only showed the current value when opened instead of all options, due to pre-filled query immediately substring-filtering. Fixed via `query === value` check. |
| [001ep-allow-patch-mapping-to-drop-signed-off-bindings](./completed/001ep-allow-patch-mapping-to-drop-signed-off-bindings.md) | Backend: patch_mapping used to 409 when removing a signed-off binding. Removed that block so deletion always succeeds; still deletes the orphaned sign-off row. Verified by executing the plan directly (20/20 tests pass, no ambiguity hit). Prerequisite for 001eq. |
| [001em-expose-destination-columns-codegen-guard](./completed/001em-expose-destination-columns-codegen-guard.md) | Exposed MappingSnapshot.destination_columns in the API (MappingDestinationColumnResponse model), populated in all 3 response builders via proper model construction; replaced silent-skip in codegen with loud destination_metadata_missing error; added 3 regression tests. Prerequisite for 001en. |
| [001en-feed-scoped-banner-unmapped-required-fields](./completed/001en-feed-scoped-banner-unmapped-required-fields.md) | Feed-scoped amber warning banner on codegen page for unmapped required destination fields; extends generateTransformationInstructionsTemplate with section 4; banner auto-appears on feed row expand; only counts approved MappingSnapshots. |
| [001ek-eliminate-python-ddl-parsing](./completed/001ek-eliminate-python-ddl-parsing.md) | Removed both regex-based DDL parsers (mapping/ddl.py and codegen/service.py's private copy); AI now reports each table's full column list (all_columns) directly, stored in new MappingSnapshot.destination_columns column. |
| [001el-preserve-signed-off-bindings-on-reanalyze](./completed/001el-preserve-signed-off-bindings-on-reanalyze.md) | Patched draft field mappings in place on re-analyze, preventing orphaned sign-offs. Re-supersedes 001df's mapping scope. |
| [001ej-shared-dialog-primitive](./completed/001ej-shared-dialog-primitive.md) | Extracted shared Dialog primitive and wired to UI components |
| [001ei-fix-mapping-snapshot-optional-typing](./completed/001ei-fix-mapping-snapshot-optional-typing.md) | 36 mypy --strict errors in approve_mapping/reject_mapping/unapprove_mapping, all one root cause (single-table branch produces list[MappingSnapshot \\| None], bulk branch produces Sequence[MappingSnapshot]); fix by making both branches query-shaped and consistent, not a type-annotation workaround |
| [001eh-codegen-preserve-raw-response](./completed/001eh-codegen-preserve-raw-response.md) | codegen/service.py and codegen/schema_analysis.py still discard raw AI response on validation failure; add AIResponseValidationError handling + db.commit() before raise, matching 001ec's fix everywhere else |
| [001eg-extract-proposal-module](./completed/001eg-extract-proposal-module.md) | Part 3/3: extract propose_mapping into mapping/proposal.py |
| [001ef-extract-snapshot-repository](./completed/001ef-extract-snapshot-repository.md) | Extracted snapshot repository functions to snapshots.py |
| [001ee-extract-ddl-parser](./completed/001ee-extract-ddl-parser.md) | Extracted DDL parser into mapping/ddl.py |
| [001ed-shared-prompt-template-class](./completed/001ed-shared-prompt-template-class.md) | [summary](./summary/001ed-shared-prompt-template-class.md) |
| [001ec-preserve-raw-response-on-validation-failure](./completed/001ec-preserve-raw-response-on-validation-failure.md) | [summary](./summary/001ec-preserve-raw-response-on-validation-failure.md) |
| [001eb-source-analysis-schema-hardening](./completed/001eb-source-analysis-schema-hardening.md) | [summary](./summary/001eb-source-analysis-schema-hardening.md) |
| [001ea-mapping-ai-schema-hardening](./completed/001ea-mapping-ai-schema-hardening.md) | [summary](./summary/001ea-mapping-ai-schema-hardening.md) |
| [001dz-unmapped-destination-fields-tracking](./completed/001dz-unmapped-destination-fields-tracking.md) | [summary](./summary/001dz-unmapped-destination-fields-tracking.md) |
| [001dy-one-to-many-field-mapping](./completed/001dy-one-to-many-field-mapping.md) | [summary](./summary/001dy-one-to-many-field-mapping.md) |
| [001df-ai-reanalysis-preservation](./completed/001df-ai-reanalysis-preservation.md) | [summary](./summary/001df-ai-reanalysis-preservation.md) |
| [001dd-consolidate-feed-ai-logs-ui](./completed/001dd-consolidate-feed-ai-logs-ui.md) | [summary](./summary/001dd-consolidate-feed-ai-logs-ui.md) |
| [001dc-fix-source-analysis-ai-log-artifact-id](./completed/001dc-fix-source-analysis-ai-log-artifact-id.md) | [summary](./summary/001dc-fix-source-analysis-ai-log-artifact-id.md) |
| [001db-drop-legacy-ai-log-columns](./completed/001db-drop-legacy-ai-log-columns.md) | [summary](./summary/001db-drop-legacy-ai-log-columns.md) |
| [001da-ai-log-viewer](./completed/001da-ai-log-viewer.md) | [summary](./summary/001da-ai-log-viewer.md) |
| [001cz-ai-call-log-feature-model](./completed/001cz-ai-call-log-feature-model.md) | [summary](./summary/001cz-ai-call-log-feature-model.md) |
| [001cx-data-driven-feed-analysis-prompts](./completed/001cx-data-driven-feed-analysis-prompts.md) | [summary](./summary/001cx-data-driven-feed-analysis.md) |
| [001cw-fix-001cv-review-findings](./completed/001cw-fix-001cv-review-findings.md) | [summary](./summary/001cw-fix-001cv-review-findings.md) |
| [001cs-shared-lookup-fibers](./completed/001cs-shared-lookup-fibers.md) | Shared lookup fallback already shipped in commit d25e18b — sourceValueMap and destinationTable fallback in place on Feed page |
| [001ct-codegen-mssql-standards](./completed/001ct-codegen-mssql-standards.md) | MSSQL standards (XACT_ABORT, THROW, MERGE OUTPUT logging, duplicate key checks) already shipped in generateCodingStandardsTemplate — verified |
| [001cv-revise-transformation-instructions-template](./completed/001cv-revise-transformation-instructions-template.md) | [summary](./summary/001cv-revise-transformation-instructions-template.md) |
| [001cu-generate-transformation-instructions](./completed/001cu-generate-transformation-instructions.md) | [summary](./summary/001cu-generate-transformation-instructions.md) |
| [001cp-migration-run-logging](./completed/001cp-migration-run-logging.md) | [summary](./summary/001cp-migration-run-logging.md) |
| [001co-ai-call-log](./completed/001co-ai-call-log.md) | [summary](./summary/001co-ai-call-log.md) |
| [001cm-slice-comment-thread](./completed/001cm-slice-comment-thread.md) | [summary](./summary/001cm-slice-comment-thread.md) |
| [001cl-review-page-edit-and-feed-thread](./completed/001cl-review-page-edit-and-feed-thread.md) | [summary](./summary/001cl-review-page-edit-and-feed-thread.md) |
| [001cq-generated-sql-schema-split](./completed/001cq-generated-sql-schema-split.md) | GeneratedSQL already split into staging_ddl, lookup_ddl, seed_data, stored_procedures — verified shipped |
| [001cn-codegen-instructions](./completed/001cn-codegen-instructions.md) | Project-wide coding standards + per-feed transformation instructions injected into AI codegen prompt |
| [001ck-copybook-unmasked-storage-approval-toggle](./completed/001ck-copybook-unmasked-storage-approval-toggle.md) | Store copybook `row_csv` unmasked; display-time masking + admin/PM toggle |
| [001cj-remove-feed-id-display](./completed/001cj-remove-feed-id-display.md) | [plan](../plans/2026-07-08-001cj-remove-feed-id-display.md) |
| [001ci-remove-project-id-display](./completed/001ci-remove-project-id-display.md) | [plan](../plans/2026-07-08-001ci-remove-project-id-display.md) |
| [001ch-pm-project-edit-access](./completed/001ch-pm-project-edit-access.md) | [plan](../plans/2026-07-08-001ch-pm-project-edit-access.md) |
| [001cg-project-member-role-filtering](./completed/001cg-project-member-role-filtering.md) | [plan](../plans/2026-07-08-001cg-project-member-role-filtering.md) |
| [001cf-admin-pm-assignment-nav](./completed/001cf-admin-pm-assignment-nav.md) | [plan](../plans/2026-07-08-001cf-admin-pm-assignment-nav.md) |
| [001ce-project-member-autocomplete](./completed/001ce-project-member-autocomplete.md) | [plan](../plans/2026-07-08-001ce-project-member-autocomplete-pm-scoping.md) |
| [001cd-pm-admin-role-model](./completed/001cd-pm-admin-role-model.md) | [plan](../plans/2026-07-08-001cd-pm-admin-role-model.md) |
| [001cc-feed-slice-approval-data-profile](./completed/001cc-feed-slice-approval-data-profile.md) | [summary](./summary/001cc-feed-slice-approval-data-profile.md) |
| [001cb-lookup-value-map-project-scope](./completed/001cb-lookup-value-map-project-scope.md) | [summary](./summary/001cb-lookup-value-map-project-scope.md) |
| [001ca-lookup-fiber-bridge](./completed/001ca-lookup-fiber-bridge.md) | [summary](./summary/001ca-lookup-fiber-bridge.md) |
| [001bw-dashboard-health-view](./completed/001bw-dashboard-health-view.md) | [summary](./summary/001bw-dashboard-health-view.md) |
| [001bv-unmapped-source-fields-warning](./completed/001bv-unmapped-source-fields-warning.md) | [summary](./summary/001bv-unmapped-source-fields-warning.md) |
| [001bt-project-copy-prompt-config](./completed/001bt-project-copy-prompt-config.md) | [summary](./summary/001bt-project-copy-prompt-config.md) |
| [001bu-feed-slice-rejection-replacement](./completed/001bu-feed-slice-rejection-replacement.md) | [summary](./summary/001bu-feed-slice-rejection-replacement.md) |
| [001br-ai-tracing-and-mapping-hints](./completed/001br-ai-tracing-and-mapping-hints.md) | [summary](./summary/001br-ai-tracing-and-mapping-hints.md) |
| [001bs-review-page-sample-data](./completed/001bs-review-page-sample-data.md) | [summary](./summary/001bs-review-page-sample-data.md) |
| [001bq-operator-mapping-edit-submit](./completed/001bq-operator-mapping-edit-submit.md) | [summary](./summary/001bq-operator-mapping-edit-submit.md) |
| [001bp-review-bulk-approve-reject](./completed/001bp-review-bulk-approve-reject.md) | [summary](./summary/001bp-review-bulk-approve-reject.md) |
| [001bo-review-page-multi-table](./completed/001bo-review-page-multi-table.md) | [summary](./summary/001bo-review-page-multi-table.md) |
| [001bn-fix-mapping-snapshot-uniqueness](./completed/001bn-fix-mapping-snapshot-uniqueness.md) | [summary](./summary/001bn-fix-mapping-snapshot-uniqueness.md) |
| [001bl-feed-workspace-slice-view-ai-trigger](./completed/001bl-feed-workspace-slice-view-ai-trigger.md) | [summary](./summary/001bl-feed-workspace-slice-view-ai-trigger.md) |
| [001bk-multi-table-snapshot-api](./completed/001bk-multi-table-snapshot-api.md) | [summary](./summary/001bk-multi-table-snapshot-api.md) |
| [001bi-lookup-fiber-two-textarea-input](./completed/001bi-lookup-fiber-two-textarea-input.md) | [summary](./summary/001bi-lookup-fiber-two-textarea-input.md) |
| [001bh-remove-feeds-tab-ddl-banner](./completed/001bh-remove-feeds-tab-ddl-banner.md) | [summary](./summary/001bh-remove-feeds-tab-ddl-banner.md) |
| [001bj-remove-feed-slice-upload](./completed/001bj-remove-feed-slice-upload.md) | [summary](./summary/001bj-remove-feed-slice-upload.md) |
| [001bg-remove-global-approvals-inbox](./completed/001bg-remove-global-approvals-inbox.md) | [summary](./summary/001bg-remove-global-approvals-inbox.md) |
| [001bf-feeds-workspace-ui](./completed/001bf-feeds-workspace-ui.md) | [summary](./summary/001bf-feeds-workspace-ui.md) |
| [001be-mapping-lookup-ui](./completed/001be-mapping-lookup-ui.md) | [summary](./summary/001be-mapping-lookup-ui.md) |
| [001bd-ai-mapping-extraction](./completed/001bd-ai-mapping-extraction.md) | [summary](./summary/001bd-ai-mapping-extraction.md) |
| [001bc-project-model-policy-default-hints](./completed/001bc-project-model-policy-default-hints.md) | [summary](./summary/001bc-project-model-policy-default-hints.md) |
| [001bb-project-edit-layout-parity](./completed/001bb-project-edit-layout-parity.md) | [summary](./summary/001bb-project-edit-layout-parity.md) |
| [001ay-project-resources-rich-editor](./completed/001ay-project-resources-rich-editor.md) | [summary](./summary/001ay-project-resources-rich-editor.md) |
| [001ax-project-resources-field](./completed/001ax-project-resources-field.md) | [summary](./summary/001ax-project-resources-field.md) |
| [001aa-reconciliation](./completed/001aa-reconciliation.md) | [summary](./summary/001aa-reconciliation.md) |
| [001ag-delivery-bundle-tab](./completed/001ag-delivery-bundle-tab.md) | [summary](./summary/001ag-delivery-bundle-tab.md) |
| [001aq-bundle-sequencing](./completed/001aq-bundle-sequencing.md) | [summary](./summary/001aq-bundle-sequencing.md) |
| [001ai-knowledge-freeze-history](./completed/001ai-knowledge-freeze-history.md) | [summary](./summary/001ai-knowledge-freeze-history.md) |
| [001ap-lookup-delta-cr-review](./completed/001ap-lookup-delta-cr-review.md) | [summary](./summary/001ap-lookup-delta-cr-review.md) |
| [001ar-dry-run-review](./completed/001ar-dry-run-review.md) | [summary](./summary/001ar-dry-run-review.md) |
| [001h-ui-portfolio-project-screens](./completed/001h-ui-portfolio-project-screens.md) | [summary](./summary/001h-ui-portfolio-project-screens.md) |
| [001i-ui-template-foundation](./completed/001i-ui-template-foundation.md) | [summary](./summary/001i-ui-template-foundation.md) |
| [001q-source-intake](./completed/001q-source-intake.md) | [summary](./summary/001q-source-intake.md) |
| [001t-runs-api](./completed/001t-runs-api.md) | [summary](./summary/001t-runs-api.md) |
| [001u-runs-ui](./completed/001u-runs-ui.md) | [summary](./summary/001u-runs-ui.md) |
| [001v-source-analysis](./completed/001v-source-analysis.md) | [summary](./summary/001v-source-analysis.md) |
| [001w-mapping-stage](./completed/001w-mapping-stage.md) | [summary](./summary/001w-mapping-stage.md) |
| [001ae-lookup-snapshot-route-rehome](./completed/001ae-lookup-snapshot-route-rehome.md) | [summary](./summary/001ae-lookup-snapshot-route-rehome.md) |
| [001l-ui-auth-api-wiring](./completed/001l-ui-auth-api-wiring.md) | [summary](./summary/001l-ui-auth-api-wiring.md) |
| [001n-ui-role-based-navigation](./completed/001n-ui-role-based-navigation.md) | [summary](./summary/001n-ui-role-based-navigation.md) |
| [001m-ui-management-user-admin](./completed/001m-ui-management-user-admin.md) | [summary](./summary/001m-ui-management-user-admin.md) |
| [001o-project-crud](./completed/001o-project-crud.md) | [summary](./summary/001o-project-crud.md) |
| [001p-project-crud-ui](./completed/001p-project-crud-ui.md) | [summary](./summary/001p-project-crud-ui.md) |
| [001ab-source-slice-approval](./completed/001ab-source-slice-approval.md) | [summary](./summary/001ab-source-slice-approval.md) |
| [001av-admin-user-edit-delete-controls](./completed/001av-admin-user-edit-delete-controls.md) | [summary](./summary/001av-admin-user-edit-delete-controls.md) |
| [001az-model-policy-overrides](./completed/001az-model-policy-overrides.md) | [summary](./summary/001az-model-policy-overrides.md) |
| [001aw-project-edit](./completed/001aw-project-edit.md) | [summary](./summary/001aw-project-edit.md) |
| [001ba-feed-slice-terminology-sweep](./completed/001ba-feed-slice-terminology-sweep.md) | Replace remaining human-facing source slice wording with feed slice terminology |
| [001ah-delivery-bundle-sequencing](./completed/001ah-delivery-bundle-sequencing.md) | [summary](./summary/001ah-delivery-bundle-sequencing.md) |
| [001x-lookup-value-mapping](./completed/001x-lookup-value-mapping.md) | [summary](./summary/001x-lookup-value-mapping.md) |
| [001y-codegen-service](./completed/001y-codegen-service.md) | [summary](./summary/001y-codegen-service.md) |
| [001ac-mapping-hardening](./completed/001ac-mapping-hardening.md) | [summary](./summary/001ac-mapping-hardening.md) |
| [001ad-runs-analysis-review-hardening](./completed/001ad-runs-analysis-review-hardening.md) | [summary](./summary/001ad-runs-analysis-review-hardening.md) |
| [001r-codegen-artifact-model](./completed/001r-codegen-artifact-model.md) | [summary](./summary/001r-codegen-artifact-model.md) |
| [001s-ai-adapters](./completed/001s-ai-adapters.md) | [summary](./summary/001s-ai-adapters.md) |
| [001j-engine-fastapi-foundation](./completed/001j-engine-fastapi-foundation.md) | [summary](./summary/001j-engine-fastapi-foundation.md) |
| [001k-api-contracts-auth](./completed/001k-api-contracts-auth.md) | [summary](./summary/001k-api-contracts-auth.md) |
| [001aj-feed-rename](./completed/001aj-feed-rename.md) | [summary](./summary/001aj-feed-rename.md) |
| [001ak-fiber-models](./completed/001ak-fiber-models.md) | [summary](./summary/001ak-fiber-models.md) |
| [001as-impact-review](./completed/001as-impact-review.md) | [summary](./summary/001as-impact-review.md) |
| [001a-login-and-session](./completed/001a-login-and-session.md) | [summary](./summary/001a-login-and-session.md) |
| [001b-password-reset](./completed/001b-password-reset.md) | [summary](./summary/001b-password-reset.md) |
| [001c-roles-and-membership](./completed/001c-roles-and-membership.md) | [summary](./summary/001c-roles-and-membership.md) |
| [001d-minimal-mapping-slice](./completed/001d-minimal-mapping-slice.md) | [summary](./summary/001d-minimal-mapping-slice.md) |
| [001an-fiber-approval-chain](./completed/001an-fiber-approval-chain.md) | [summary](./summary/001an-fiber-approval-chain.md) |
| [001af-ui-compliance-gaps](./completed/001af-ui-compliance-gaps.md) | [summary](./summary/001af-ui-compliance-gaps.md) |
| [001at-notifications](./completed/001at-notifications.md) | [summary](./summary/001at-notifications.md) |

## Archived / Superseded

| Task | Superseded By | Notes |
|---|---|---|
| [001e-ui-shell](./001e-ui-shell.md) | 001i, 001l, 001n | Shell/tokens → 001i; auth → 001l (done); role nav → 001n (done) |
| [001f-ui-shell-and-tokens](./001f-ui-shell-and-tokens.md) | 001i | Subset of 001i scope |
| [001g-ui-auth-and-login](./001g-ui-auth-and-login.md) | 001l (completed) | Login + session routing shipped in 001l |
| [001fa-lookup-fiber-rewrite](./001fa-lookup-fiber-rewrite.md) | |
