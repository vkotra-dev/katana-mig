import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminLayout from "./layout";

const { loadUiSessionMock, replaceMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("../../components/Topbar", () => ({
  Topbar: ({ role }: { role: string }) => <header>Topbar for {role}</header>,
}));

vi.mock("../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

describe("AdminLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders children for pm users", async () => {
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "pm",
      sessionVersion: 1,
      userId: "user-1",
    });

    render(
      <AdminLayout>
        <div>Admin content</div>
      </AdminLayout>
    );

    expect(await screen.findByText("Topbar for pm")).toBeInTheDocument();
    expect(await screen.findByText("Admin content")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("renders children for admin users", async () => {
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "admin",
      sessionVersion: 1,
      userId: "user-1",
    });

    render(
      <AdminLayout>
        <div>Admin content</div>
      </AdminLayout>
    );

    expect(await screen.findByText("Topbar for admin")).toBeInTheDocument();
    expect(await screen.findByText("Admin content")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("redirects non-admin/pm users to the home page", async () => {
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });

    render(
      <AdminLayout>
        <div>Admin content</div>
      </AdminLayout>
    );

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/"));
    expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
  });
});
