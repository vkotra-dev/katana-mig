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

- Allow `central_team` to manage users.
- Allow `central_team` to assign and remove project memberships.
- Allow users to change their own password.
- Reject user-management actions from insufficient roles.
- Keep role assignment authoritative and auditable.
- Support first-time bootstrap creation of an administrative user.
- Support project membership for `project_stakeholder` users.

## Out of scope

- Login mechanics.
- Session/token issuance.
- Project routing and registry behavior.
- Approval workflow semantics.
- Fine-grained business authorization beyond role and membership checks.

## Relationship to other pages

- Authentication mechanics are defined in `auth.md`.
- Security boundaries are defined in `security.md`.
- Project-scoped access rules are defined in `specs/18-project-registry.md`.
- UI role surfaces are defined in `specs/28-ui.md`.
- Approval gate role requirements are defined in
  `specs/29-approval-service.md`.

## Role model

Current platform roles:

- `central_team`
- `project_stakeholder`
- `read_only_auditor`

`service_account` is not a platform role. It is an integration principal used
for non-human channels and is managed by authentication/credential policy, not
by the user- and membership-management flows here.

Role meaning:

- `central_team` is the administrative role. It can manage users and project
  membership and has cross-project operational authority.
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

Project membership binds a `project_stakeholder` user to a project.

Relevant fields:

- `project_id`
- `user_id`
- `created_at`

Membership rows exist only for project-scoped stakeholders. `central_team` and
`read_only_auditor` do not need membership rows.

## Administrative flows

### Create user

`central_team` can create a new user.

The create flow must:

- require an authenticated `central_team` caller
- validate the requested role
- hash the password before persistence
- reject duplicate email addresses
- emit audit evidence

### Update user

`central_team` can update a user’s profile and role.

The update flow must:

- require an authenticated `central_team` caller
- preserve role validity
- keep historical auditability of the change
- reject updates to nonexistent users

### Soft-delete user

`central_team` can soft-delete a user.

The delete flow must:

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

`central_team` can add or remove `project_stakeholder` users from a project.

The flow must:

- require an authenticated `central_team` caller
- reject membership for non-stakeholder roles
- prevent duplicate memberships
- preserve project isolation

### Bootstrap admin

The system must support creation of the first `central_team` user when the user
table is empty.

Bootstrap may occur via:

- startup seed from environment variables
- CLI bootstrap path

Bootstrap must be idempotent. Once users exist, the seed path must not create
duplicates.

## User and membership rules

- A user’s role is a platform-level attribute.
- Project membership is separate from role.
- `project_stakeholder` role alone is not enough for project access; membership
  is also required.
- `central_team` does not require per-project membership.
- `read_only_auditor` reads broadly without administrative power.

## Enforcement rules

### User management

- `POST /users` requires `central_team`.
- `GET /users` requires `central_team`.
- `GET /users/{user_id}` requires `central_team` or self.
- `PATCH /users/{user_id}` requires `central_team`.
- `DELETE /users/{user_id}` requires `central_team`.

### Membership management

- `GET /projects/{project_id}/members` requires `central_team`.
- `POST /projects/{project_id}/members` requires `central_team`.
- `DELETE /projects/{project_id}/members/{user_id}` requires `central_team`.
- A stakeholder creating a project should be auto-added as a member.

### Role and request-body authority

- Role fields in request bodies are not authoritative for authorization.
- Role must come from authenticated state.
- Any role change must be an explicit administrative action.

## Failure modes

| Situation | Handling |
|-----------|----------|
| Non-admin attempts user creation | Reject |
| Non-admin attempts role change | Reject |
| Duplicate email on user create | Reject |
| Membership assigned to non-stakeholder role | Reject |
| Duplicate project membership | Reject or no-op, but must be explicit |
| Soft-deleted user attempts login or action | Reject |
| Bootstrap invoked when users already exist | No duplicate creation |
| Bootstrap credentials missing or invalid | Fail closed |

## Acceptance criteria

- [ ] `central_team` can create, update, and soft-delete users.
- [ ] `central_team` can assign and remove project memberships.
- [ ] `project_stakeholder` cannot manage users or memberships.
- [ ] `read_only_auditor` cannot manage users or memberships.
- [ ] A stakeholder’s project access depends on membership, not role alone.
- [ ] The first admin user can be bootstrapped idempotently.
- [ ] Administrative actions are auditable.
- [ ] Password changes do not allow role escalation.

## Open questions

- Should role updates be allowed directly, or only via a dedicated role-change
  flow with extra confirmation?
- Should duplicate membership creation be rejected or silently treated as a
  no-op?
- Should project membership assignment trigger notifications?
- Should bootstrap admin be startup-only, CLI-only, or both in production?

## Changelog

- 2026-06-29: Added dedicated management page for user CRUD, role assignment,
  project membership, and bootstrap admin behavior.
