import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RunsPage from "./page";

const {
  getUiSessionMock,
  listProjectsMock,
  listRunsMock,
  routerPushMock,
} = vi.hoisted(() => ({
  getUiSessionMock: vi.fn(),
  listProjectsMock: vi.fn(),
  listRunsMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock("../../lib/session", () => ({
  getUiSession: getUiSessionMock,
  loadUiSession: getUiSessionMock,
}));

vi.mock("../../lib/projects-api", () => ({
  listProjects: listProjectsMock,
}));

vi.mock("../../lib/runs-api", () => ({
  listRuns: listRunsMock,
  resumeRun: vi.fn(),
}));

vi.mock("../../components/runs/LaunchRunDialog", () => ({
  LaunchRunDialog: ({ open }: { open: boolean }) => (open ? <div>Launch dialog</div> : null),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPushMock,
  }),
}));

describe("RunsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    listProjectsMock.mockResolvedValue([
      {
        projectId: "project-1",
        name: "Alpha Migration",
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
        status: "active",
        createdAt: "2026-06-30T00:00:00Z",
        updatedAt: "2026-06-30T00:00:00Z",
        archivedAt: null,
      },
    ]);
    listRunsMock.mockResolvedValue([
      {
        run_id: "run-1",
        project_id: "project-1",
        destination_object_name: "Customer",
        source_definition_reference: "source-1",
        environment: "dev",
        status: "paused",
        current_stage: "mapping",
        source_slice_version: "v1",
        mapping_snapshot_version: "v1",
        lookup_snapshot_version: "v1",
        code_generation_input_snapshot_version: "v1",
        codegen_artifact_id: null,
        knowledge_freeze_version: null,
        start_metadata: null,
        pause_metadata: null,
        resume_metadata: null,
        completion_metadata: null,
        started_at: "2026-06-30T00:00:00Z",
        last_checkpoint_at: "2026-06-30T00:10:00Z",
        created_at: "2026-06-30T00:00:00Z",
        updated_at: "2026-06-30T00:10:00Z",
      },
    ]);
  });

  it("renders the runs table and launch entry point", async () => {
    render(<RunsPage />);

    expect(await screen.findByText("Customer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Launch run" })).toBeInTheDocument();
    expect(screen.getByText("paused", { selector: "span[data-status='paused']" })).toBeInTheDocument();
  });

  it("filters by status and project", async () => {
    render(<RunsPage />);

    await screen.findByText("Customer");
    fireEvent.change(screen.getAllByRole("combobox")[1], { target: { value: "project-1" } });
    fireEvent.change(screen.getAllByRole("combobox")[3], { target: { value: "paused" } });

    expect(screen.getByText("Customer")).toBeInTheDocument();
  });

  it("shows an empty state when there are no runs", async () => {
    listRunsMock.mockResolvedValue([]);

    render(<RunsPage />);

    expect(await screen.findByText("No runs yet.")).toBeInTheDocument();
  });
});
