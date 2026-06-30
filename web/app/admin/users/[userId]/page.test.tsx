import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import UserDetailPage from "./page";

const { loadUiSessionMock, getUserMock, updateUserMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getUserMock: vi.fn(),
  updateUserMock: vi.fn(),
}));

vi.mock("../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../lib/management-api", () => ({
  getUser: getUserMock,
  updateUser: updateUserMock,
}));

describe("UserDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    getUserMock.mockResolvedValue({
      userId: "user-2",
      email: "stakeholder@example.com",
      displayName: "Stakeholder",
      role: "project_stakeholder",
      status: "active",
      createdAt: "2026-06-29T12:00:00Z",
      updatedAt: "2026-06-29T12:00:00Z",
    });
    updateUserMock.mockResolvedValue({
      userId: "user-2",
      email: "stakeholder@example.com",
      displayName: "Updated Stakeholder",
      role: "project_stakeholder",
      status: "disabled",
      createdAt: "2026-06-29T12:00:00Z",
      updatedAt: "2026-06-29T12:00:00Z",
    });
  });

  it("loads the user and saves updates", async () => {
    render(<UserDetailPage params={{ userId: "user-2" }} />);

    expect(await screen.findByDisplayValue("stakeholder@example.com")).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("Stakeholder"), {
      target: { value: "Updated Stakeholder" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement);

    await waitFor(() =>
      expect(updateUserMock).toHaveBeenCalledWith("token-1", "user-2", {
        displayName: "Updated Stakeholder",
        role: "project_stakeholder",
        status: "active",
      })
    );
  });
});
