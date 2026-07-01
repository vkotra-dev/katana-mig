# Task Index

## Ready

| Task | Summary | Depends on |
|---|---|---|
| [001al-lookup-fiber-ai-flow](./001al-lookup-fiber-ai-flow.md) | lookup_mapping AI slot, lookup inputs endpoint, AI proposals | 001ak |
| [001am-mapping-fiber-ai-flow](./001am-mapping-fiber-ai-flow.md) | feed_analysis AI slot, analyze_feed endpoint, field bindings | 001ak |
| [001as-impact-review](./001as-impact-review.md) | impact_analysis AI slot, GET impact + acknowledge routes, review screen | — |
| [001at-notifications](./001at-notifications.md) | Notification model (0017), 4 endpoints, NotificationBell component with polling | — |
| [001ao-feed-comment](./001ao-feed-comment.md) | FeedComment model (0020), thread endpoint, notifications | 001ak |
| [001an-fiber-approval-chain](./001an-fiber-approval-chain.md) | 3-step: operator assign → business approve → operator trigger + fiber detail page | 001al, 001am |
| [001ai-knowledge-freeze-history](./001ai-knowledge-freeze-history.md) | Read-only freeze history panel in project detail Overview tab | — |
| [001ap-lookup-delta-cr-review](./001ap-lookup-delta-cr-review.md) | List/get/resolve CR endpoints + review page (no new DB model) | 001ai |
| [001ar-dry-run-review](./001ar-dry-run-review.md) | DryRunArtifact model, GET/approve/push-back routes, review screen | 001ak |

## Later Phase

| Task | Summary | Depends on |
|---|---|---|
| [001ag-delivery-bundle-tab](./001ag-delivery-bundle-tab.md) | Add SQL Bundle tab to project detail page navigating to codegen page | — |
| [001ah-delivery-bundle-sequencing](./001ah-delivery-bundle-sequencing.md) | AI DDL analysis, FK-ordered delivery bundle, SourceList banner, codegen report panel | — |
| [001aq-bundle-sequencing](./001aq-bundle-sequencing.md) | Lookup upsert SQL generator, trigger_fiber codegen, 0000/0001+ bundle ordering | 001ah, 001ak |

## Completed

| Task | Summary |
|---|---|
| [001aa-reconciliation](./completed/001aa-reconciliation.md) | [summary](./summary/001aa-reconciliation.md) |
| [001af-ui-compliance-gaps](./completed/001af-ui-compliance-gaps.md) | [summary](./summary/001af-ui-compliance-gaps.md) |
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
| [001a-login-and-session](./completed/001a-login-and-session.md) | [summary](./summary/001a-login-and-session.md) |
| [001b-password-reset](./completed/001b-password-reset.md) | [summary](./summary/001b-password-reset.md) |
| [001c-roles-and-membership](./completed/001c-roles-and-membership.md) | [summary](./summary/001c-roles-and-membership.md) |
| [001d-minimal-mapping-slice](./completed/001d-minimal-mapping-slice.md) | [summary](./summary/001d-minimal-mapping-slice.md) |
| [001af-ui-compliance-gaps](./completed/001af-ui-compliance-gaps.md) | [summary](./summary/001af-ui-compliance-gaps.md) |

## Archived / Superseded

| Task | Superseded By | Notes |
|---|---|---|
| [001e-ui-shell](./001e-ui-shell.md) | 001i, 001l, 001n | Shell/tokens → 001i; auth → 001l (done); role nav → 001n (done) |
| [001f-ui-shell-and-tokens](./001f-ui-shell-and-tokens.md) | 001i | Subset of 001i scope |
| [001g-ui-auth-and-login](./001g-ui-auth-and-login.md) | 001l (completed) | Login + session routing shipped in 001l |
