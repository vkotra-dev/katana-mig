# Task Index

| Task | Domain | Status | Notes |
|---|---|---|---|
| [001h-ui-portfolio-project-screens](./001h-ui-portfolio-project-screens.md) | ui, project | ready | **Narrowed**: portfolio dashboard only (stitch 02); project detail → 001p; run progress → 001u |
| [001i-ui-template-foundation](./001i-ui-template-foundation.md) | ui | ready | Shell, tokens, Topbar/Sidebar/LoginView from mockmigration templates |
| [001o-project-crud](./001o-project-crud.md) | project, api, management | ready | Project lifecycle backend — create, list, get, update, archive |
| [001p-project-crud-ui](./001p-project-crud-ui.md) | ui, project | ready | Five-step project initiation wizard (stitch 07) + project list + detail view |
| [001q-source-intake](./001q-source-intake.md) | source-model, api, ui | ready | CSV and fixed-length source intake; Sources tab on project detail |
| [001ab-source-slice-approval](./001ab-source-slice-approval.md) | source-model, api, ui | ready | Approve/reject/resubmit flow for parsed slices; Approvals page; depends on 001q |
| [001r-codegen-artifact-model](./001r-codegen-artifact-model.md) | source-model, runs | ready | CodeGenerationArtifact ORM model + migration 0009; depends on 001q (0008) |
| [001s-ai-adapters](./001s-ai-adapters.md) | ai | ready | AI adapter layer — Anthropic SDK, env key reading, structured output interface |
| [001t-runs-api](./001t-runs-api.md) | runs, source-model, governance | ready | Run CRUD, launch, execution engine, checkpoint writes, LookupDeltaCR; depends on 001q/r/s |
| [001u-runs-ui](./001u-runs-ui.md) | ui, runs | ready | Runs list, run detail (5 tabs, polling), launch dialog; stitch 03/04/05; depends on 001t |
| [001v-source-analysis](./001v-source-analysis.md) | source-model, ai | ready | AI analysis of SourceSlice → SourceSchemaArtifact + SourceValueSummary; migration 0011 |
| [001w-mapping-stage](./001w-mapping-stage.md) | source-model, api, ui | ready | AI-proposed field bindings, mapping approval, destination_object_references baton |
| [001x-lookup-value-mapping](./001x-lookup-value-mapping.md) | source-model, api, ui | ready | LookupValueMap entry UI, LookupSnapshot creation + approval; migration 0012 |
| [001y-codegen-service](./001y-codegen-service.md) | source-model, ai, runs | ready | AI generates sql_bundle → CodeGenerationArtifact; supersession; delivery bundle API |
| [001z-review-gates](./001z-review-gates.md) | governance, ui | ready | Gate 1 + Gate 2 approval backend + UI (stitch 08–10); depends on 001y |
| [001aa-reconciliation](./001aa-reconciliation.md) | governance, ui | ready | Reconciliation checks + ReconciliationReport; stitch 11; depends on 001t, 001z |

## Completed

| Task | Summary |
|---|---|
| [001l-ui-auth-api-wiring](./completed/001l-ui-auth-api-wiring.md) | [summary](./summary/001l-ui-auth-api-wiring.md) |
| [001n-ui-role-based-navigation](./completed/001n-ui-role-based-navigation.md) | [summary](./summary/001n-ui-role-based-navigation.md) |
| [001m-ui-management-user-admin](./completed/001m-ui-management-user-admin.md) | [summary](./summary/001m-ui-management-user-admin.md) |
| [001j-engine-fastapi-foundation](./completed/001j-engine-fastapi-foundation.md) | [summary](./summary/001j-engine-fastapi-foundation.md) |
| [001k-api-contracts-auth](./completed/001k-api-contracts-auth.md) | [summary](./summary/001k-api-contracts-auth.md) |
| [001a-login-and-session](./completed/001a-login-and-session.md) | [summary](./summary/001a-login-and-session.md) |
| [001b-password-reset](./completed/001b-password-reset.md) | [summary](./summary/001b-password-reset.md) |
| [001c-roles-and-membership](./completed/001c-roles-and-membership.md) | [summary](./summary/001c-roles-and-membership.md) |
| [001d-minimal-mapping-slice](./completed/001d-minimal-mapping-slice.md) | [summary](./summary/001d-minimal-mapping-slice.md) |

## Archived / Superseded

| Task | Superseded By | Notes |
|---|---|---|
| [001e-ui-shell](./001e-ui-shell.md) | 001i, 001l, 001n | Shell/tokens → 001i; auth → 001l (done); role nav → 001n (done) |
| [001f-ui-shell-and-tokens](./001f-ui-shell-and-tokens.md) | 001i | Subset of 001i scope |
| [001g-ui-auth-and-login](./001g-ui-auth-and-login.md) | 001l (completed) | Login + session routing shipped in 001l |
