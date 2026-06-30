import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewUserPage from "./page";

const { loadUiSessionMock, createUserMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  createUserMock: vi.fn(),
}));

vi.mock("../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../lib/management-api", () => ({
  createUser: createUserMock,
}));

describe("NewUserPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    createUserMock.mockResolvedValue({
      userId: "user-2",
      email: "stakeholder@example.com",
      displayName: "Stakeholder",
      role: "project_stakeholder",
      status: "active",
      createdAt: "2026-06-29T12:00:00Z",
      updatedAt: "2026-06-29T12:00:00Z",
    });
  });

  it("creates a new user and shows success", async () => {
    render(<NewUserPage />);

    fireEvent.change(screen.getByPlaceholderText("operator@example.com"), {
      target: { value: "stakeholder@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("Initial password"), {
      target: { value: "password-123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Operator"), {
      target: { value: "Stakeholder" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Create user" }).closest("form") as HTMLFormElement);

    await waitFor(() =>
      expect(createUserMock).toHaveBeenCalledWith("token-1", {
        email: "stakeholder@example.com",
        password: "password-123",
        displayName: "Stakeholder",
        role: "project_stakeholder",
      })
    );
    expect(await screen.findByText("User created successfully.")).toBeInTheDocument();
  });
});
