# 001f-ui-shell-and-tokens

## Domain

- [ui.md](/Users/vjkotra/projects/katana/docs/domain/ui.md)
- [security.md](/Users/vjkotra/projects/katana/docs/domain/security.md)

## Objective

Build the strict UI shell from the supplied Stitch screen and token set:
sticky top navigation, dense content canvas, light surfaces, indigo primary
accent, and the exact spacing/typography scale provided in the design snippet.

## Scope

- Global CSS variables and base typography tokens
- Sticky top nav and shared app shell layout
- Search box, project chip, and user/avatar cluster
- Desktop-first dense shell structure that matches the supplied screen

## Out of Scope

- Login form and authentication flows
- Portfolio and project-specific data cards
- Migration, mapping, or reconciliation content

## Acceptance Criteria

- The shell uses the supplied token values as the source of truth
- The top nav, brand area, and content canvas match the supplied layout shape
- The UI does not introduce a conflicting color system or spacing scale

## Test Expectations

- The rendered layout uses the supplied CSS custom properties
- The sticky header and content canvas render in the expected positions
- The shell remains visually consistent across desktop viewport sizes

