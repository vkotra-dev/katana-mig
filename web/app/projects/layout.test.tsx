import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectsLayout from "./layout";

const { loadUiSessionMock, pathnameMock, replaceMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  pathnameMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameMock(),
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

describe("ProjectsLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pathnameMock.mockReturnValue("/projects");
  });

  it("renders project list children for global access", async () => {
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });

    render(
      <ProjectsLayout>
        <div>Projects content</div>
      </ProjectsLayout>
    );

    expect(await screen.findByText("Projects content")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("rejects project-stakeholder access when the project is not in scope", async () => {
    pathnameMock.mockReturnValue("/projects/project-1");
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "project_stakeholder",
      sessionVersion: 1,
      userId: "user-1",
      projectIds: ["project-2"],
    });

    render(
      <ProjectsLayout>
        <div>Projects content</div>
      </ProjectsLayout>
    );

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/"));
    expect(screen.queryByText("Projects content")).not.toBeInTheDocument();
  });
});
