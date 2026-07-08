import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectMembersPage from "./page";

const { loadUiSessionMock, listProjectMembersMock, listUsersMock, addProjectMemberMock, removeProjectMemberMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  listProjectMembersMock: vi.fn(),
  listUsersMock: vi.fn(),
  addProjectMemberMock: vi.fn(),
  removeProjectMemberMock: vi.fn(),
}));

const { getProjectMock, assignProjectManagerMock } = vi.hoisted(() => ({
  getProjectMock: vi.fn(),
  assignProjectManagerMock: vi.fn(),
}));

vi.mock("../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../lib/management-api", () => ({
  listProjectMembers: listProjectMembersMock,
  listUsers: listUsersMock,
  addProjectMember: addProjectMemberMock,
  removeProjectMember: removeProjectMemberMock,
}));

vi.mock("../../../../../lib/projects-api", () => ({
  getProject: getProjectMock,
  assignProjectManager: assignProjectManagerMock,
  projectErrorMessage: (e: any) => e.message,
}));

describe("ProjectMembersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "admin",
      sessionVersion: 1,
      userId: "user-1",
    });
    getProjectMock.mockResolvedValue({
      projectId: "project-1",
      name: "Project 1",
      goal: "Goal",
      repos: [],
      workspace: {},
      pmUserId: null,
      status: "active",
      createdAt: "2026-06-29T12:00:00Z",
      updatedAt: "2026-06-29T12:00:00Z",
      archivedAt: null,
    });
    listProjectMembersMock.mockResolvedValue([
      {
        projectId: "project-1",
        userId: "user-2",
        createdAt: "2026-06-29T12:00:00Z",
      },
    ]);
    listUsersMock.mockResolvedValue([
      {
        userId: "user-2",
        email: "stakeholder@example.com",
        displayName: "Stakeholder",
        role: "project_stakeholder",
        status: "active",
        createdAt: "2026-06-29T12:00:00Z",
        updatedAt: "2026-06-29T12:00:00Z",
      },
      {
        userId: "user-3",
        email: "other@example.com",
        displayName: "Other User",
        role: "project_stakeholder",
        status: "active",
        createdAt: "2026-06-29T12:00:00Z",
        updatedAt: "2026-06-29T12:00:00Z",
      },
      {
        userId: "pm-1",
        email: "pm1@example.com",
        displayName: "Project Manager 1",
        role: "pm",
        status: "active",
        createdAt: "2026-06-29T12:00:00Z",
        updatedAt: "2026-06-29T12:00:00Z",
      },
    ]);
    addProjectMemberMock.mockResolvedValue({
      projectId: "project-1",
      userId: "user-3",
      warning: "User is already a member of this project.",
    });
    removeProjectMemberMock.mockResolvedValue(undefined);
    assignProjectManagerMock.mockResolvedValue({
      projectId: "project-1",
      name: "Project 1",
      goal: "Goal",
      repos: [],
      workspace: {},
      pmUserId: "pm-1",
      status: "active",
      createdAt: "2026-06-29T12:00:00Z",
      updatedAt: "2026-06-29T12:00:00Z",
      archivedAt: null,
    });
  });

  it("renders members and supports add/remove/PM-assign actions", async () => {
    render(<ProjectMembersPage params={{ projectId: "project-1" }} />);

    expect(await screen.findByText("stakeholder@example.com")).toBeInTheDocument();

    // Add member action
    const memberInput = screen.getByPlaceholderText("Search users by email or name...");
    fireEvent.focus(memberInput);
    fireEvent.change(memberInput, {
      target: { value: "other" },
    });
    const memberOption = await screen.findByText("other@example.com — Other User (project_stakeholder)");
    fireEvent.click(memberOption);

    await waitFor(() =>
      expect(addProjectMemberMock).toHaveBeenCalledWith("token-1", "project-1", "user-3")
    );

    // Remove member action
    screen.getByRole("button", { name: "Remove" }).click();
    await waitFor(() => expect(removeProjectMemberMock).toHaveBeenCalledWith("token-1", "project-1", "user-2"));

    // PM assign action
    const pmInput = screen.getByPlaceholderText("Search Project Managers...");
    fireEvent.focus(pmInput);
    fireEvent.change(pmInput, {
      target: { value: "pm1" },
    });
    const pmOption = await screen.findByText("pm1@example.com — Project Manager 1");
    fireEvent.click(pmOption);

    await waitFor(() =>
      expect(assignProjectManagerMock).toHaveBeenCalledWith("token-1", "project-1", "pm-1")
    );
  });
});
