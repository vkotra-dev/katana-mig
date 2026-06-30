import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RunDetailPage from "./page";

const {
  getUiSessionMock,
  listProjectsMock,
  listRunsMock,
  getRunMock,
  listCheckpointsMock,
  resumeRunMock,
  useParamsMock,
  useSearchParamsMock,
} = vi.hoisted(() => ({
  getUiSessionMock: vi.fn(),
  listProjectsMock: vi.fn(),
  listRunsMock: vi.fn(),
  getRunMock: vi.fn(),
  listCheckpointsMock: vi.fn(),
  resumeRunMock: vi.fn(),
  useParamsMock: vi.fn(),
  useSearchParamsMock: vi.fn(),
}));

vi.mock("../../../lib/session", () => ({
  getUiSession: getUiSessionMock,
  loadUiSession: getUiSessionMock,
}));

vi.mock("../../../lib/projects-api", () => ({
  listProjects: listProjectsMock,
}));

vi.mock("../../../lib/runs-api", () => ({
  getRun: getRunMock,
  listRuns: listRunsMock,
  listCheckpoints: listCheckpointsMock,
  resumeRun: resumeRunMock,
}));

vi.mock("next/navigation", () => ({
  useParams: () => useParamsMock(),
  useSearchParams: () => useSearchParamsMock(),
  useRouter: () => ({ push: vi.fn() }),
}));

describe("RunDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    useParamsMock.mockReturnValue({ id: "run-1" });
    useSearchParamsMock.mockReturnValue(new URLSearchParams("projectId=project-1"));
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
    getRunMock.mockResolvedValue({
      run_id: "run-1",
      project_id: "project-1",
      destination_object_name: "Customer",
      source_definition_reference: "source-1",
      environment: "dev",
      status: "awaiting_approval",
      current_stage: "mapping",
      source_slice_version: "v1",
      mapping_snapshot_version: "v1",
      lookup_snapshot_version: "v1",
      lookup_snapshot_versions: {
        status_map: "v1",
      },
      code_generation_input_snapshot_version: "v1",
      codegen_artifact_id: "cga-1234",
      knowledge_freeze_version: "cga-1234",
      start_metadata: {
        started_at: "2026-06-30T00:00:00Z",
      },
      pause_metadata: {
        pause_reason: "lookup_delta",
        paused_at: "2026-06-30T00:10:00Z",
      },
      resume_metadata: null,
      completion_metadata: null,
      started_at: "2026-06-30T00:00:00Z",
      last_checkpoint_at: "2026-06-30T00:10:00Z",
      created_at: "2026-06-30T00:00:00Z",
      updated_at: "2026-06-30T00:10:00Z",
    });
    listRunsMock.mockResolvedValue([]);
    listCheckpointsMock.mockResolvedValue([
      {
        checkpoint_id: "checkpoint-1",
        run_id: "run-1",
        stage: "mapping",
        current_object: "Customer",
        current_environment: "dev",
        approved_snapshots: {
          source_slice_version: "v1",
          lookup_snapshot_versions: {
            status_map: "v1",
          },
        },
        last_completed_row: 499,
        pause_reason: "lookup_delta",
        created_at: "2026-06-30T00:10:00Z",
      },
    ]);
    resumeRunMock.mockResolvedValue({
      run_id: "run-1",
      project_id: "project-1",
      destination_object_name: "Customer",
      source_definition_reference: "source-1",
      environment: "dev",
      status: "running",
      current_stage: "mapping",
      source_slice_version: "v1",
      mapping_snapshot_version: "v1",
      lookup_snapshot_version: "v2",
      lookup_snapshot_versions: {
        status_map: "v2",
      },
      code_generation_input_snapshot_version: "v1",
      codegen_artifact_id: "cga-1234",
      knowledge_freeze_version: "cga-1234",
      start_metadata: null,
      pause_metadata: null,
      resume_metadata: {
        resumed_at: "2026-06-30T00:20:00Z",
      },
      completion_metadata: null,
      started_at: "2026-06-30T00:00:00Z",
      last_checkpoint_at: "2026-06-30T00:10:00Z",
      created_at: "2026-06-30T00:00:00Z",
      updated_at: "2026-06-30T00:20:00Z",
    });
  });

  it("renders the detail header, tabs, and paused banner", async () => {
    render(<RunDetailPage />);

    expect(await screen.findByText("Alpha Migration")).toBeInTheDocument();
    expect(screen.getByText("Awaiting approval")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Resume" }).length).toBeGreaterThan(0);
  });

  it("shows pinned snapshots and checkpoints", async () => {
    render(<RunDetailPage />);

    await screen.findByText("Alpha Migration");
    fireEvent.click(screen.getByRole("button", { name: "Pinned snapshots" }));
    expect(screen.getByText("cga_cga-1234")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Checkpoints" }));
    expect(screen.getByText("499")).toBeInTheDocument();
  });

  it("resumes the run from the banner", async () => {
    render(<RunDetailPage />);

    await screen.findByText("Alpha Migration");
    fireEvent.click(screen.getAllByRole("button", { name: "Resume" })[0]);

    await waitFor(() => expect(resumeRunMock).toHaveBeenCalledWith("token-1", "project-1", "run-1"));
  });
});
