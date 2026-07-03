# Delivery Bundle Tab Design

## Goal

Add a fourth project-detail tab, `SQL Bundle`, that links to the existing codegen
page. The same tab row should appear on the codegen page with `SQL Bundle`
shown as the active tab.

## Current State

The project detail page currently renders three tabs:

- `Overview`
- `Sources`
- `Artifacts`

The codegen page already exists at `/projects/[id]/codegen`, but it does not use
the same tab row as the project detail page. The current implementation therefore
surfaces code generation as a standalone page rather than as part of the project
navigation.

## Intended Behavior

### Project detail page

Route: `/projects/[id]`

The tab row should contain four pills:

- `Overview`
- `Sources`
- `Artifacts`
- `SQL Bundle`

Clicking `SQL Bundle` should navigate to `/projects/[id]/codegen` with
`router.push`.

### Codegen page

Route: `/projects/[id]/codegen`

The same four-pill tab row should appear at the top of the page.

- `SQL Bundle` is the active tab
- `Overview`, `Sources`, and `Artifacts` should navigate back to `/projects/[id]`
- The codegen page content itself remains unchanged

### Role handling

The tab row is visible to all roles exactly as it is today for the existing tabs.
This change does not introduce any new role gate or permission rule.

## Approach

Use a shared tab-row component or a shared tab configuration constant if the
existing page structure makes that simpler. The important part is that both pages
render the same tab labels and active-state behavior without duplicating route
strings in an inconsistent way.

Recommended shape:

- one shared tab definition list
- one small renderer used by both pages
- project detail marks `Overview` active by default
- codegen marks `SQL Bundle` active by default

## Scope

In scope:

- project detail tab row
- codegen page tab row
- navigation behavior between the two pages
- tests for both routes

Out of scope:

- backend API changes
- permission model changes
- codegen page content changes
- new tabs beyond `SQL Bundle`

## Success Criteria

- `SQL Bundle` appears on the project detail page and routes to `/projects/[id]/codegen`
- the codegen page shows the same tab row with `SQL Bundle` active
- the codegen page keeps its existing content and behavior
- all touched tests pass

## Verification

- update the project detail page test to assert the new tab and click behavior
- update the codegen page test to assert the active tab state
- run the frontend test suite
