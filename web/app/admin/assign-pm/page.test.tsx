import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AssignPmPage from "./page";

const { loadUiSessionMock, listProjectsMock, listUsersMock, assignProjectManagerMock, routerReplaceMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  listProjectsMock: vi.fn(),
  listUsersMock: vi.fn(),
  assignProjectManagerMock: vi.fn(),
  routerReplaceMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: routerReplaceMock,
  }),
}));

vi.mock("../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../lib/projects-api", () => ({
  listProjects: listProjectsMock,
  assignProjectManager: assignProjectManagerMock,
}));

vi.mock("../../../lib/management-api", () => ({
  listUsers: listUsersMock,
}));

describe("AssignPmPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-admin",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "admin",
      sessionVersion: 1,
      userId: "user-admin",
    });
    listProjectsMock.mockResolvedValue([
      {
        projectId: "proj-active",
        name: "Active Project",
        status: "active",
        createdAt: "2026-06-30T12:00:00Z",
        updatedAt: "2026-06-30T12:00:00Z",
        archivedAt: null,
      },
      {
        projectId: "proj-archived",
        name: "Archived Project",
        status: "archived",
        createdAt: "2026-06-30T12:00:00Z",
        updatedAt: "2026-06-30T12:00:00Z",
        archivedAt: "2026-07-01T12:00:00Z",
      },
    ]);
    listUsersMock.mockResolvedValue([
      {
        userId: "user-pm-active",
        email: "pm-active@example.com",
        displayName: "Active PM",
        role: "pm",
        status: "active",
        createdAt: "2026-06-30T12:00:00Z",
        updatedAt: "2026-06-30T12:00:00Z",
      },
      {
        userId: "user-pm-inactive",
        email: "pm-inactive@example.com",
        displayName: "Inactive PM",
        role: "pm",
        status: "suspended",
        createdAt: "2026-06-30T12:00:00Z",
        updatedAt: "2026-06-30T12:00:00Z",
      },
      {
        userId: "user-sh",
        email: "sh@example.com",
        displayName: "Stakeholder",
        role: "project_stakeholder",
        status: "active",
        createdAt: "2026-06-30T12:00:00Z",
        updatedAt: "2026-06-30T12:00:00Z",
      },
    ]);
    assignProjectManagerMock.mockResolvedValue(undefined);
  });

  it("redirects non-admin users to home", async () => {
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-pm",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "pm",
      sessionVersion: 1,
      userId: "user-pm",
    });
    render(<AssignPmPage />);
    expect(routerReplaceMock).toHaveBeenCalledWith("/");
  });

  it("performs PM assignment workflow with active-only filters", async () => {
    render(<AssignPmPage />);

    expect(await screen.findByRole("heading", { name: "Assign Project Manager" })).toBeInTheDocument();

    const projectInput = await screen.findByPlaceholderText("Search active projects by name...");
    const pmInput = screen.getByPlaceholderText("Search Project Managers by email or name...");

    fireEvent.focus(projectInput);
    fireEvent.change(projectInput, { target: { value: "Project" } });

    expect(screen.getByText("Active Project", { selector: "li" })).toBeInTheDocument();
    expect(screen.queryByText("Archived Project")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Active Project", { selector: "li" }));
    expect(projectInput).toHaveValue("Active Project");

    fireEvent.focus(pmInput);
    fireEvent.change(pmInput, { target: { value: "PM" } });

    expect(screen.getByText("pm-active@example.com — Active PM", { selector: "li" })).toBeInTheDocument();
    expect(screen.queryByText("pm-inactive@example.com — Inactive PM")).not.toBeInTheDocument();
    expect(screen.queryByText("sh@example.com — Stakeholder")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("pm-active@example.com — Active PM", { selector: "li" }));
    expect(pmInput).toHaveValue("pm-active@example.com — Active PM");

    const submitBtn = screen.getByRole("button", { name: "Assign Project Manager" });
    expect(submitBtn).toBeEnabled();
    fireEvent.click(submitBtn);

    await waitFor(() =>
      expect(assignProjectManagerMock).toHaveBeenCalledWith("token-admin", "proj-active", "user-pm-active")
    );

    expect(
      await screen.findByText(/Successfully assigned Project Manager "Active PM" to project "Active Project"/i)
    ).toBeInTheDocument();
    expect(projectInput).toHaveValue("");
    expect(pmInput).toHaveValue("");
  });
});
