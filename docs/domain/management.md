---
type: Domain Spec
title: Management
description: Administrative management of users, roles, and project membership — admin-gated user CRUD, PM-gated member assignment, and the 5-role enforcement model.
tags:
  - management
  - users
  - roles
  - membership
  - admin
timestamp: 2026-07-16
---

# Management

This page defines administrative management of users, roles, and project
membership for the migration platform.

It sits on top of authentication. Auth proves who the caller is; management
defines who can create identities, change roles, assign project membership, and
seed the first administrative account.

## Purpose

Provide a governed administrative model for:

- creating and maintaining users
- assigning and changing roles
- soft-deleting users
- managing project membership for project-scoped stakeholders
- bootstrapping the first administrative identity
- preserving auditability for administrative actions

This is the operational control surface for who can participate in the system
and at what level.

## Responsibilities

- Allow `admin` to manage users (create, edit, soft-delete, assign roles).
- Allow `pm` to assign and remove project memberships for their projects.
- Allow users to change their own password.
- Reject user-management actions from insufficient roles.
- Keep role assignment authoritative and auditable.
- Support first-time bootstrap creation of an administrative user.
- Support project membership for `central_team` and `project_stakeholder` users.

## Out of scope

- Login mechanics.
- Session/token issuance.
- Project routing and registry behavior.
- Approval workflow semantics.
- Fine-grained business authorization beyond role and membership checks.

## Relationship to other pages

- Authentication mechanics are defined in `auth.md`.
- Security boundaries are defined in `security.md`.
- Project-scoped access rules are defined in `project.md` and `runs.md`.
- UI role surfaces are defined in `ui.md`.
- Approval gate role requirements are enforced by the approval-service route
  in the harness bundle.

## Role model

Current platform roles:

- `admin`
- `pm`
- `central_team`
- `project_stakeholder`
- `read_only_auditor`

`service_account` is not a platform role. It is an integration principal used
for non-human channels and is managed by authentication/credential policy, not
by the user- and membership-management flows here.

Role meaning:

- `admin` is the user-management role. It can create, edit, soft-delete users
  and assign roles. It can also reassign the PM on any project. Route guard:
  `get_admin_user`.
- `pm` is the project-lifecycle role. It can create, copy, and edit projects,
  assign project members, and owns projects via `pm_user_id` on
  `ProjectRegistry`. Route guard: `get_pm_user`.
- `central_team` is the in-project operator role. It requires explicit project
  membership and can perform in-project work (mapping, codegen, review,
  approval) only on assigned projects. It no longer has global project access
  or user-management authority.
- `project_stakeholder` is project-scoped. It can act only on projects it is
  assigned to.
- `read_only_auditor` is view-only. It cannot manage users or membership.

## Data model

### User

User records are shared platform identities.

Relevant fields:

- `user_id`
- `email`
- `display_name`
- `password_hash`
- `role`
- `status`
- `soft_deleted_at`
- `created_at`
- `updated_at`

### Project membership

Project membership binds a `central_team` or `project_stakeholder` user to a
project.

Relevant fields:

- `project_id`
- `user_id`
- `created_at`

Membership rows are required for `central_team` and `project_stakeholder`
users. `admin`, `pm`, and `read_only_auditor` do not use membership rows.
Member autocomplete filters to only `central_team` and `project_stakeholder`
roles (excludes `admin` and `pm`).

## Administrative flows

### Create user

`admin` can create a new user.

The create flow must:

- require an authenticated `admin` caller (route guard: `get_admin_user`)
- validate the requested role against the five canonical roles
- hash the password before persistence
- reject duplicate email addresses
- emit audit evidence

### Update user

`admin` can update a user's profile and role.

The update flow must:

- require an authenticated `admin` caller (route guard: `get_admin_user`)
- allow role edits directly in the user update flow
- preserve role validity across all five canonical roles
- keep historical auditability of the change
- reject updates to nonexistent users
- treat the role change as an explicit administrative action in audit records

### Soft-delete user

`admin` can soft-delete a user.

The delete flow must:

- require an authenticated `admin` caller (route guard: `get_admin_user`)
- mark the user inactive rather than hard-delete
- prevent future login and request use
- keep prior audit and history intact

### Self-service password change

An authenticated user can change their own password.

The flow must:

- require the current authenticated identity
- verify the existing password or equivalent challenge
- store only the new hash
- not allow role escalation through the password-change path

### Assign project membership

`pm` can add or remove `central_team` and `project_stakeholder` users from
projects they own.

The flow must:

- require an authenticated `pm` caller (route guard: `get_pm_user`)
- reject membership for roles other than `central_team` and
  `project_stakeholder`
- treat duplicate membership as an idempotent no-op with a warning that the
  user is already part of the project
- preserve project isolation
- trigger a notification to the affected user when membership is added or
  removed

### Reassign project manager

`admin` can reassign the PM on any project via
`PATCH /projects/{id}/manager`.

The flow must:

- require an authenticated `admin` caller (route guard: `get_admin_user`)
- update `pm_user_id` on the `ProjectRegistry` record
- reject assignment to a user who does not hold the `pm` role
- emit audit evidence

### Bootstrap admin

The system must support creation of the first `admin` user when the user table
is empty.

Bootstrap may occur via:

- startup seed from environment variables
- CLI bootstrap path

Bootstrap must be idempotent. Once users exist, the seed path must not create
duplicates.

## User and membership rules

- A user's role is a platform-level attribute.
- Project membership is separate from role.
- `project_stakeholder` role alone is not enough for project access; membership
  is also required.
- `central_team` requires per-project membership; it no longer has global
  project access.
- `admin` and `pm` do not require per-project membership.
- `read_only_auditor` reads broadly without administrative power.

## Enforcement rules

### User management

- `POST /users` requires `admin`.
- `GET /users` requires `admin`.
- `GET /users/{user_id}` requires `admin` or self.
- `PATCH /users/{user_id}` requires `admin`.
- `DELETE /users/{user_id}` requires `admin`.

### Membership management

- `GET /projects/{project_id}/members` requires `pm` (project owner) or
  `admin`.
- `POST /projects/{project_id}/members` requires `pm` (project owner).
- `DELETE /projects/{project_id}/members/{user_id}` requires `pm` (project
  owner).
- `PATCH /projects/{id}/manager` requires `admin` (reassign PM).
- A `pm` creating a project is auto-recorded as the project's `pm_user_id`.

### Role and request-body authority

- Role fields in request bodies are not authoritative for authorization.
- Role must come from authenticated state.
- Role changes may be submitted directly in the user update request, but they
  are still explicit administrative actions and must be audited as such.

## Failure modes

| Situation | Handling |
|-----------|----------|
| Non-admin attempts user creation | Reject |
| Non-admin attempts role change | Reject |
| Duplicate email on user create | Reject |
| Membership assigned to role other than `central_team` or `project_stakeholder` | Reject |
| Duplicate project membership | No-op with warning |
| Soft-deleted user attempts login or action | Reject |
| Bootstrap invoked when users already exist | No duplicate creation |
| Bootstrap credentials missing or invalid | Fail closed |

## Acceptance criteria

- [ ] `admin` can create, update, and soft-delete users.
- [ ] `pm` can assign and remove project memberships for owned projects.
- [ ] `central_team` cannot manage users or memberships.
- [ ] `project_stakeholder` cannot manage users or memberships.
- [ ] `read_only_auditor` cannot manage users or memberships.
- [ ] `central_team` project access depends on membership, not role alone.
- [ ] A stakeholder's project access depends on membership, not role alone.
- [ ] The first admin user can be bootstrapped idempotently.
- [ ] Administrative actions are auditable.
- [ ] Password changes do not allow role escalation.
- [ ] PM reassignment is admin-only and audited.

## Open questions

- ~Should project membership assignment trigger notifications?~ — **Resolved:**
  yes, implemented in task 001at.
- Should bootstrap admin be startup-only, CLI-only, or both in production?

## Changelog

- 2026-06-29: Added dedicated management page for user CRUD, role assignment,
  project membership, and bootstrap admin behavior.
- 2026-06-29: Clarified that role edits happen directly in the user update
  flow and are audited as explicit administrative actions.
- 2026-06-29: Clarified that duplicate project membership is an idempotent
  no-op with a warning.
- 2026-07-16: Roles expanded from 3 to 5 (`admin`, `pm` added);
  `central_team` scoped to project membership; user CRUD gated by `admin`;
  membership managed by `pm`; PM reassignment flow added; open question on
  membership notifications resolved.
