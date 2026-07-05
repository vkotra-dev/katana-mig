import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProjectDetailPage from "./page";

const {
  loadUiSessionMock,
  getProjectMock,
  getAiModelDefaultsMock,
  routerPushMock,
  searchParamsGetMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getProjectMock: vi.fn(),
  getAiModelDefaultsMock: vi.fn(),
  routerPushMock: vi.fn(),
  searchParamsGetMock: vi.fn(),
}));

vi.mock("../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../lib/projects-api", () => ({
  getProject: getProjectMock,
  projectErrorMessage: (e: unknown) => (e instanceof Error ? e.message : "Error"),
}));

vi.mock("../../../lib/ai-model-defaults-api", () => ({
  getAiModelDefaults: getAiModelDefaultsMock,
}));

vi.mock("../../../components/projects/ProjectDetailView", () => ({
  ProjectDetailView: (props: { modelDefaults: Record<string, string> | null }) => (
    <div>
      <div>Overview content</div>
      <div data-testid="model-defaults">{JSON.stringify(props.modelDefaults)}</div>
    </div>
  ),
}));

vi.mock("../../../components/projects/SourceList", () => ({
  SourceList: () => <div>Sources content</div>,
}));

vi.mock("../../../components/projects/SourceArtifactsPanel", () => ({
  SourceArtifactsPanel: () => <div>Artifacts content</div>,
}));

vi.mock("../../../components/projects/KnowledgeFreezePanel", () => ({
  KnowledgeFreezePanel: () => <div>Knowledge freeze</div>,
}));

vi.mock("../../../components/Topbar", () => ({
  Topbar: () => <nav>Topbar</nav>,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
  useSearchParams: () => ({ get: searchParamsGetMock }),
}));

const SESSION = {
  accessToken: "tok-1",
  expiresAt: "2027-01-01T00:00:00Z",
  role: "project_stakeholder" as const,
  sessionVersion: 1,
  userId: "user-1",
};

const CENTRAL_TEAM_SESSION = {
  accessToken: "tok-3",
  expiresAt: "2027-01-01T00:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-3",
};

const AUDITOR_SESSION = {
  accessToken: "tok-2",
  expiresAt: "2027-01-01T00:00:00Z",
  role: "read_only_auditor" as const,
  sessionVersion: 1,
  userId: "user-2",
};

const PROJECT = {
  projectId: "proj-1",
  name: "Alpha",
  goal: null,
  repos: null,
  workspace: null,
  environment: null,
  executionEnvironments: null,
  modelPolicy: null,
  canonicalTerms: null,
  constraints: null,
  unresolvedQuestions: null,
  assumptions: null,
  domainConfig: null,
  lexiconScope: null,
  status: "active" as const,
  createdAt: "2026-07-01T00:00:00Z",
  updatedAt: "2026-07-01T00:00:00Z",
  archivedAt: null,
  latestRunSummary: null,
};

async function renderPage(id: string) {
  await act(async () => {
    render(<ProjectDetailPage params={Promise.resolve({ id })} />);
  });
}

describe("ProjectDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamsGetMock.mockReturnValue(null);
    loadUiSessionMock.mockReturnValue(SESSION);
    getProjectMock.mockResolvedValue(PROJECT);
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
  });

  it("renders the SQL Bundle tab button", async () => {
    await renderPage("proj-1");
    expect(await screen.findByRole("button", { name: "SQL Bundle" })).toBeInTheDocument();
  });

  it("navigates to codegen page when SQL Bundle tab is clicked", async () => {
    await renderPage("proj-1");
    const tab = await screen.findByRole("button", { name: "SQL Bundle" });
    fireEvent.click(tab);
    expect(routerPushMock).toHaveBeenCalledWith("/projects/proj-1/codegen");
  });

  it("renders the SQL Bundle tab for read-only auditors too", async () => {
    loadUiSessionMock.mockReturnValue(AUDITOR_SESSION);
    await renderPage("proj-1");
    expect(await screen.findByRole("button", { name: "SQL Bundle" })).toBeInTheDocument();
  });

  it("shows an edit link for central team users", async () => {
    loadUiSessionMock.mockReturnValue(CENTRAL_TEAM_SESSION);
    await renderPage("proj-1");
    expect(await screen.findByRole("link", { name: "Edit" })).toHaveAttribute("href", "/projects/proj-1/edit");
  });

  it("hides edit for read-only auditors", async () => {
    loadUiSessionMock.mockReturnValue(AUDITOR_SESSION);
    await renderPage("proj-1");
    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("restores the requested project tab from the query string (feeds/sources mapping)", async () => {
    searchParamsGetMock.mockImplementation((key: string) => (key === "tab" ? "sources" : null));
    await renderPage("proj-1");
    expect(await screen.findByRole("button", { name: "Feeds" })).toHaveClass("bg-primary");
  });

  it("passes the model defaults into the project detail view", async () => {
    await renderPage("proj-1");

    expect(await screen.findByText("Overview content")).toBeInTheDocument();
    expect(getAiModelDefaultsMock).toHaveBeenCalledWith("tok-1");
    expect(screen.getByTestId("model-defaults")).toHaveTextContent("field-model");
  });
});
