import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectEditPage from "./page";
import type { ProjectRecord } from "../../../../lib/projects-api";

const {
  loadUiSessionMock,
  getProjectMock,
  getAiModelDefaultsMock,
  updateProjectMock,
  routerPushMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getProjectMock: vi.fn(),
  getAiModelDefaultsMock: vi.fn(),
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
    destinationSchema: "dbo",
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

vi.mock("../../../../lib/ai-model-defaults-api", () => ({
  getAiModelDefaults: getAiModelDefaultsMock,
}));

vi.mock("../../../../components/Topbar", () => ({
  Topbar: () => <nav>Topbar</nav>,
}));

vi.mock("../../../../components/projects/ProjectEditForm", () => ({
  ProjectEditForm: (props: {
    modelDefaults: Record<string, string> | null;
    project: ProjectRecord;
  }) => (
    <div>
      <div>Project edit form</div>
      <div data-testid="model-defaults">{JSON.stringify(props.modelDefaults)}</div>
      <div data-testid="project-name">{props.project.name}</div>
    </div>
  ),
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
    getAiModelDefaultsMock.mockResolvedValue({
      source: "engine.yaml",
      platformModels: {
        planning: "planning-model",
        review: "review-model",
        implementation: "implementation-model",
      },
      migrationModels: {
        piiReview: "pii-model",
        fieldMapping: "field-model",
        lookupMapping: "lookup-model",
        scriptGeneration: "script-generation-model",
        scriptCorrection: "script-correction-model",
        schemaDependency: "schema-dependency-model",
        impactAnalysis: "impact-model",
        feedAnalysis: "feed-analysis-model",
      },
    });
    updateProjectMock.mockResolvedValue(project);
  });

  async function renderPage(id: string) {
    await act(async () => {
      render(<ProjectEditPage params={Promise.resolve({ id })} />);
    });
  }

  it("loads the project and passes model defaults into the form", async () => {
    await renderPage("proj-1");

    expect(await screen.findByText("Project edit form")).toBeInTheDocument();
    expect(screen.getByTestId("project-name")).toHaveTextContent("CRM Migration");
    await waitFor(() => expect(getAiModelDefaultsMock).toHaveBeenCalledWith("tok-1"));
    expect(screen.getByTestId("model-defaults")).toHaveTextContent("field-model");
  });
});
