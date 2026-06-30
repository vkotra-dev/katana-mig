import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminUsersPage from "./page";

const { loadUiSessionMock, listUsersMock, deleteUserMock, replaceMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  listUsersMock: vi.fn(),
  deleteUserMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../lib/management-api", () => ({
  listUsers: listUsersMock,
  deleteUser: deleteUserMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

describe("AdminUsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    listUsersMock.mockResolvedValue([
      {
        userId: "user-2",
        email: "stakeholder@example.com",
        displayName: "Stakeholder",
        role: "project_stakeholder",
        status: "active",
      },
    ]);
    deleteUserMock.mockResolvedValue(undefined);
  });

  it("renders the user list and create-user entry point", async () => {
    render(<AdminUsersPage />);

    expect(await screen.findByText("stakeholder@example.com")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create user" })).toHaveAttribute("href", "/admin/users/new");
  });

  it("deletes a user from the list", async () => {
    render(<AdminUsersPage />);

    await screen.findByText("stakeholder@example.com");
    screen.getByRole("button", { name: "Delete" }).click();

    await waitFor(() => expect(deleteUserMock).toHaveBeenCalledWith("token-1", "user-2"));
  });
});
