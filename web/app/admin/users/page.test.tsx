import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminUsersPage from "./page";

const { loadUiSessionMock, listUsersMock, deleteUserMock, pushMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  listUsersMock: vi.fn(),
  deleteUserMock: vi.fn(),
  pushMock: vi.fn(),
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
    push: pushMock,
  }),
}));

describe("AdminUsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "admin",
      sessionVersion: 1,
      userId: "user-1",
    });
    listUsersMock.mockResolvedValueOnce([
      {
        userId: "user-2",
        email: "stakeholder@example.com",
        displayName: "Stakeholder",
        role: "project_stakeholder",
        status: "active",
      },
    ]);
    listUsersMock.mockResolvedValue([]);
    deleteUserMock.mockResolvedValue(undefined);
  });

  it("renders the user list and create-user entry point", async () => {
    render(<AdminUsersPage />);

    expect(await screen.findByText("stakeholder@example.com")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create user" })).toHaveAttribute("href", "/admin/users/new");
  });

  it("routes to the user detail page for edit and refreshes after delete", async () => {
    render(<AdminUsersPage />);

    await screen.findByText("stakeholder@example.com");
    screen.getByRole("button", { name: "Edit" }).click();
    expect(pushMock).toHaveBeenCalledWith("/admin/users/user-2");

    screen.getByRole("button", { name: "Delete" }).click();

    await waitFor(() => expect(deleteUserMock).toHaveBeenCalledWith("token-1", "user-2"));
    await waitFor(() => expect(listUsersMock).toHaveBeenCalledTimes(2));
    expect(screen.queryByText("stakeholder@example.com")).not.toBeInTheDocument();
  });

  it("shows an inline error when delete fails", async () => {
    deleteUserMock.mockRejectedValueOnce(new Error("Unable to delete user."));

    render(<AdminUsersPage />);

    await screen.findByText("stakeholder@example.com");
    screen.getByRole("button", { name: "Delete" }).click();

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to delete user.");
  });

  it("hides user creation and modification controls for pm role", async () => {
    loadUiSessionMock.mockReset();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "pm",
      sessionVersion: 1,
      userId: "user-1",
    });

    render(<AdminUsersPage />);

    expect(await screen.findByText("stakeholder@example.com")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Create user" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });
});
