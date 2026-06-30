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

vi.mock("../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../lib/management-api", () => ({
  listProjectMembers: listProjectMembersMock,
  listUsers: listUsersMock,
  addProjectMember: addProjectMemberMock,
  removeProjectMember: removeProjectMemberMock,
}));

describe("ProjectMembersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
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
    ]);
    addProjectMemberMock.mockResolvedValue({
      projectId: "project-1",
      userId: "user-3",
      warning: "User is already a member of this project.",
    });
    removeProjectMemberMock.mockResolvedValue(undefined);
  });

  it("renders members and supports add/remove actions", async () => {
    render(<ProjectMembersPage params={{ projectId: "project-1" }} />);

    expect(await screen.findByText("stakeholder@example.com")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("User ID"), {
      target: { value: "user-3" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Add member" }).closest("form") as HTMLFormElement);

    await waitFor(() =>
      expect(addProjectMemberMock).toHaveBeenCalledWith("token-1", "project-1", "user-3")
    );
    expect(await screen.findByText("User is already a member of this project.")).toBeInTheDocument();
    screen.getByRole("button", { name: "Remove" }).click();
    await waitFor(() => expect(removeProjectMemberMock).toHaveBeenCalledWith("token-1", "project-1", "user-2"));
  });
});
