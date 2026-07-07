# Task 001bt Summary — Project Copy: Carry Forward Prompt Config

Implemented the backend and frontend support for cloning projects to enable recurring migrations.

## Backend
1. **API Schema**: Added `ProjectCopyRequest` schema accepting `name` and `stakeholder_user_ids`.
2. **Management Logic**: Implemented `copy_project` in `management/projects.py`. It clones the registry and definition records, copying configurations verbatim while skipping history (slices, runs, snapshots, comment threads). It loops over `Feed` records and duplicates them (including `mapping_hints` and nested layout parameters). Finally, it populates membership fields for the specified new stakeholders and creates a management audit log `project.copied`.
3. **Route**: Connected `POST /projects/{project_id}/copy` route, protected for `central_team` users only.
4. **Tests**: Added full CRUD test suite coverage verifying constraints duplication, mapping hints carry-over, archived project check, and stakeholder access.

## Frontend
1. **API Client**: Implemented the `copyProject` service call in `web/lib/projects-api.ts`.
2. **Initiate Dropdown**: Replaced the "Initiate Project" button with a modern chevron dropdown displaying "New Project" and "Copy from..." options on the Projects list page.
3. **Copy Modal**: Built a premium two-step modal:
   - **Step 1**: Filters and searches active, non-archived projects.
   - **Step 2**: Prompts for the new project's name (defaulting to "Copy of [source]") and allows assigning a fresh set of stakeholder user IDs.
4. **Tests**: Updated `ProjectTable.test.tsx` to align with the new dropdown flow and verified `onCopyClick` and `onInitiate` triggers.
