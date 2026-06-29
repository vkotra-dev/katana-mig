# Domain Index

This folder is the active working set for the project.

The pages here are the canonical domain docs for the new project basis. They are
grouped by concern so the system can be understood without chasing the older
spec archive.

This folder is intended to be sufficient for day-to-day planning, tasking, and
implementation decisions. The numbered specs are retained for lineage and
archive updates.

## Areas

| Domain | Page |
|---|---|
| Governance | [`governance.md`](./governance.md) |
| Harness | [`harness.md`](./harness.md) |
| Launch gate | [`launch-gate.md`](./launch-gate.md) |
| Security | [`security.md`](./security.md) |
| Auth | [`auth.md`](./auth.md) |
| Management | [`management.md`](./management.md) |
| UI | [`ui.md`](./ui.md) |
| Project | [`project.md`](./project.md) |
| Runs | [`runs.md`](./runs.md) |
| Source model | [`source-model.md`](./source-model.md) |

## Reading order

1. [`project.md`](./project.md)
2. [`source-model.md`](./source-model.md)
3. [`runs.md`](./runs.md)
4. [`governance.md`](./governance.md)
5. [`harness.md`](./harness.md)
6. [`launch-gate.md`](./launch-gate.md)
7. [`auth.md`](./auth.md)
8. [`management.md`](./management.md)
9. [`ui.md`](./ui.md)
10. [`security.md`](./security.md)

The older `specs/` tree remains as historical record. Read this folder first;
use the numbered specs only when you need derivation history or are updating
the archive deliberately.

## Spec Funnel Map

This bundle is consolidated from the numbered specs, but it is the working view
for the repo. Use the numbered specs for lineage, cross-checking, or deliberate
archive updates.

| Bundle page | Numbered specs funneled in |
|---|---|
| `governance.md` | repo rules, task workflow, build order, invariants, typing/testing conventions |
| `harness.md` | `00`–`19`, `30`–`32` |
| `project.md` | `16`, `18` and the project-facing portions of `11`, `17`, `28`, `29`, `38` |
| `runs.md` | `01`, `08`, `12`, `17`, `24`, `26`, `27`, `39`, `41`, `42`, `43` |
| `source-model.md` | `16`, `20`–`27`, `39`, `40`, `41`, `42`, `43` |
| `auth.md` | auth/user model material from `28`, `29`, `32`, `38` plus session authority from the repo rulebook |
| `management.md` | user CRUD, role assignment, and membership flows from `28`, `29`, `18`, `38` |
| `ui.md` | operator surface from `16`, `18`, `28`, `29`, `31`, `32`, and the domain bundle pages |
| `security.md` | identity, PII, audit, and isolation rules from `05`, `08`, `12`, `18`, `22`, `29`, `31`, `32` and the repo rulebook |
