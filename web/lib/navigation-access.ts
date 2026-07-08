import type { SessionRole } from "./session";

export type VisibleAction =
  | "manage-users"
  | "manage-memberships"
  | "gate-2-review"
  | "lookup-delta-review"
  | "reconciliation-read";

export function canAccessAdmin(role: SessionRole): boolean {
  return role === "admin" || role === "pm";
}

export function canAccessProject(
  role: SessionRole,
  projectId: string,
  projectIds: string[],
): boolean {
  if (role === "admin") {
    return false;
  }
  if (role === "pm" || role === "read_only_auditor") {
    return true;
  }

  return projectIds.includes(projectId);
}

export function visibleActionsForRole(role: SessionRole): VisibleAction[] {
  switch (role) {
    case "admin":
      return ["manage-users"];
    case "pm":
      return ["manage-memberships"];
    case "central_team":
      return ["gate-2-review", "reconciliation-read"];
    case "project_stakeholder":
      return ["gate-2-review", "lookup-delta-review", "reconciliation-read"];
    case "read_only_auditor":
      return ["reconciliation-read"];
  }
}
