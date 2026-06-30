import { describe, expect, it } from "vitest";
import { canAccessAdmin, canAccessProject, visibleActionsForRole } from "./navigation-access";

describe("navigation-access", () => {
  it("allows admin access only for central_team", () => {
    expect(canAccessAdmin("central_team")).toBe(true);
    expect(canAccessAdmin("project_stakeholder")).toBe(false);
    expect(canAccessAdmin("read_only_auditor")).toBe(false);
  });

  it("allows project access for member stakeholders and global roles", () => {
    expect(canAccessProject("central_team", "project-1", [])).toBe(true);
    expect(canAccessProject("read_only_auditor", "project-1", [])).toBe(true);
    expect(canAccessProject("project_stakeholder", "project-1", ["project-1"])).toBe(true);
    expect(canAccessProject("project_stakeholder", "project-1", ["project-2"])).toBe(false);
  });

  it("returns role-specific visible actions", () => {
    expect(visibleActionsForRole("central_team")).toContain("manage-users");
    expect(visibleActionsForRole("project_stakeholder")).toContain("lookup-delta-review");
    expect(visibleActionsForRole("read_only_auditor")).not.toContain("manage-users");
  });
});
