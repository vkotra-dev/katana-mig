import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HomePage from "../page";

const {
  loadUiSessionMock,
  saveUiSessionMock,
  clearUiSessionMock,
  fetchSessionMock,
  loginMock,
  logoutMock,
  bootstrapStatusMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  saveUiSessionMock: vi.fn(),
  clearUiSessionMock: vi.fn(),
  fetchSessionMock: vi.fn(),
  loginMock: vi.fn(),
  logoutMock: vi.fn(),
  bootstrapStatusMock: vi.fn(),
}));

vi.mock("../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
  saveUiSession: saveUiSessionMock,
  clearUiSession: clearUiSessionMock,
}));

vi.mock("../../lib/auth-api", () => ({
  fetchSession: fetchSessionMock,
  login: loginMock,
  logout: logoutMock,
  getBootstrapStatus: bootstrapStatusMock,
  requestPasswordReset: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));

describe("HomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue(null);
    bootstrapStatusMock.mockResolvedValue({ bootstrap_required: false });
    loginMock.mockResolvedValue({
      accessToken: "token-123",
      tokenType: "bearer",
      expiresAt: "2026-06-30T12:00:00Z",
      sessionVersion: 1,
      projectIds: ["project-1"],
      user: {
        user_id: "user-1",
        email: "operator@example.com",
        display_name: "Operator",
        role: "central_team",
        status: "active",
      },
    });
    fetchSessionMock.mockResolvedValue({
      user_id: "user-1",
      email: "operator@example.com",
      display_name: "Operator",
      role: "central_team",
      status: "active",
      expires_at: "2026-06-30T12:00:00Z",
      session_version: 1,
      project_ids: ["project-1"],
    });
  });

  it("renders the login form when no session exists", async () => {
    render(<HomePage />);

    expect(screen.getByText("Restoring your session...")).toBeInTheDocument();
    await waitFor(() => expect(bootstrapStatusMock).toHaveBeenCalled());
    expect(screen.getByText("Katana Console")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Log out" })).not.toBeInTheDocument();
  });

  it("logs in and switches to the authenticated shell", async () => {
    render(<HomePage />);

    fireEvent.change(await screen.findByPlaceholderText("operator@katana.io"), {
      target: { value: "operator@example.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("••••••••••••"), {
      target: { value: "secret-password" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Log in" }).closest("form") as HTMLFormElement);

    await waitFor(() => expect(loginMock).toHaveBeenCalledWith("operator@example.com", "secret-password"));
    await waitFor(() =>
      expect(saveUiSessionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          projectIds: ["project-1"],
        })
      )
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument());
  });

  it("restores the authenticated shell from a stored session", async () => {
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-abc",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      projectIds: ["project-1"],
      sessionVersion: 2,
      userId: "user-1",
    });

    render(<HomePage />);

    expect(screen.getByText("Restoring your session...")).toBeInTheDocument();
    await waitFor(() => expect(fetchSessionMock).toHaveBeenCalledWith("token-abc"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument());
  });
});
