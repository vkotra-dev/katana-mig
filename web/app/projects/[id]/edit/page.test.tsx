import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectEditPage from "./page";
import type { ProjectRecord } from "../../../../lib/projects-api";

const { loadUiSessionMock, getProjectMock, updateProjectMock, routerPushMock } = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getProjectMock: vi.fn(),
  updateProjectMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

const project: ProjectRecord = {
  projectId: "proj-1",
  name: "CRM Migration",
  goal: "Migrate all CRM data",
  repos: null,
  workspace: null,
  environment: "PROD",
  executionEnvironments: ["STG", "UAT", "PROD"],
  modelPolicy: null,
  canonicalTerms: null,
  constraints: ["GDPR", "Art 6(1)(c)"],
  unresolvedQuestions: ["PHI present?"],
  assumptions: ["Source replica is stable"],
  domainConfig: {
    targetDbEngine: "mssql",
    stagingSchema: "stg",
    dryRun: false,
    samplePolicy: null,
    destinationSchemaDdl: "create table crm(id int);",
    environments: ["dev", "uat", "prod"],
  },
  lexiconScope: null,
  status: "active",
  createdAt: "2026-06-30T00:00:00Z",
  updatedAt: "2026-06-30T01:00:00Z",
  archivedAt: null,
  latestRunSummary: null,
};

vi.mock("../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../lib/projects-api", () => ({
  getProject: getProjectMock,
  updateProject: updateProjectMock,
  projectErrorMessage: (error: unknown) => (error instanceof Error ? error.message : "Error"),
}));

vi.mock("../../../../components/Topbar", () => ({
  Topbar: () => <nav>Topbar</nav>,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

describe("ProjectEditPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "tok-1",
      expiresAt: "2027-01-01T00:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    getProjectMock.mockResolvedValue(project);
    updateProjectMock.mockResolvedValue(project);
  });

  async function renderPage(id: string) {
    await act(async () => {
      render(<ProjectEditPage params={Promise.resolve({ id })} />);
    });
  }

  it("loads the project and saves updates", async () => {
    await renderPage("proj-1");

    expect(await screen.findByRole("button", { name: "Overview" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));
    expect(routerPushMock).toHaveBeenCalledWith("/projects/proj-1");
    fireEvent.click(screen.getByRole("button", { name: "Sources" }));
    expect(routerPushMock).toHaveBeenCalledWith("/projects/proj-1?tab=sources");
    fireEvent.click(screen.getByRole("button", { name: "Artifacts" }));
    expect(routerPushMock).toHaveBeenCalledWith("/projects/proj-1?tab=artifacts");
    expect(await screen.findByDisplayValue("CRM Migration")).toBeInTheDocument();
    fireEvent.submit(
      screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement,
    );

    await waitFor(() =>
      expect(updateProjectMock).toHaveBeenCalledWith("tok-1", "proj-1", expect.any(Object)),
    );
  });
});
