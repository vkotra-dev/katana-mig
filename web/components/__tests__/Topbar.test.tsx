import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { Topbar } from "../Topbar";

const { logoutMock, loadUiSessionMock, clearUiSessionMock } = vi.hoisted(() => ({
  logoutMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
  clearUiSessionMock: vi.fn(),
}));

vi.mock("../../lib/auth-api", () => ({
  logout: logoutMock,
}));

vi.mock("../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
  clearUiSession: clearUiSessionMock,
}));

describe("Topbar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "pm",
      sessionVersion: 1,
      userId: "user-1",
    });
  });

  it("renders the Katana brand and role-aware navigation", () => {
    render(<Topbar role="pm" />);
    expect(screen.getByText("Katana")).toBeInTheDocument();
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.queryByLabelText("Search")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
  });

  it("renders Admin dropdown for admin role and opens sub-items on click", async () => {
    render(<Topbar role="admin" />);
    const adminBtn = screen.getByRole("button", { name: /Admin/i });
    expect(adminBtn).toBeInTheDocument();

    expect(screen.queryByText("Manage Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Assign PM to Project")).not.toBeInTheDocument();

    fireEvent.click(adminBtn);

    expect(screen.getByText("Manage Users")).toBeInTheDocument();
    expect(screen.getByText("Assign PM to Project")).toBeInTheDocument();
  });

  it("hides admin and approvals for read-only auditors", () => {
    render(<Topbar role="read_only_auditor" />);

    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.queryByText("Approvals")).not.toBeInTheDocument();
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });

  it("logs out from the shared header", async () => {
    render(<Topbar role="pm" />);

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => expect(logoutMock).toHaveBeenCalledWith("token-1"));
    expect(clearUiSessionMock).toHaveBeenCalled();
  });
});
