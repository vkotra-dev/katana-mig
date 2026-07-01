import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LaunchRunDialog } from "./LaunchRunDialog";

const {
  listProjectsMock,
  listFeedContractsMock,
  listFeedSlicesMock,
  listRunsMock,
  createRunMock,
  launchRunMock,
  getUiSessionMock,
} = vi.hoisted(() => ({
  listProjectsMock: vi.fn(),
  listFeedContractsMock: vi.fn(),
  listFeedSlicesMock: vi.fn(),
  listRunsMock: vi.fn(),
  createRunMock: vi.fn(),
  launchRunMock: vi.fn(),
  getUiSessionMock: vi.fn(),
}));

vi.mock("../../lib/projects-api", () => ({
  listProjects: listProjectsMock,
}));

vi.mock("../../lib/feeds-api", () => ({
  listFeedContracts: listFeedContractsMock,
  listFeedSlices: listFeedSlicesMock,
}));

vi.mock("../../lib/runs-api", () => ({
  listRuns: listRunsMock,
  createRun: createRunMock,
  launchRun: launchRunMock,
}));

vi.mock("../../lib/session", () => ({
  getUiSession: getUiSessionMock,
}));

describe("LaunchRunDialog", () => {
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
    listFeedContractsMock.mockResolvedValue([
      {
        sourceDefinitionId: "source-1",
        projectId: "project-1",
        sourceType: "csv",
        label: "Customer Extract",
        encoding: "utf-8",
        destinationObjectReferences: ["Customer"],
        layoutInformation: null,
        copybookText: null,
        status: "active",
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-1",
        sourceDefinitionId: "source-1",
        sourceSliceVersion: "v1",
        headerCsv: "STATUS",
        rowCount: 1,
        status: "approved",
        approvalRejectionReason: null,
        parseWarnings: [],
        previewRows: ["A"],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);
    listRunsMock.mockResolvedValue([]);
    createRunMock.mockResolvedValue({
      run_id: "run-1",
      project_id: "project-1",
      destination_object_name: "Customer",
      source_definition_reference: "source-1",
      environment: "dev",
      status: "queued",
      current_stage: null,
      source_slice_version: null,
      mapping_snapshot_version: null,
      lookup_snapshot_version: null,
      lookup_snapshot_versions: null,
      code_generation_input_snapshot_version: null,
      codegen_artifact_id: null,
      knowledge_freeze_version: null,
      start_metadata: null,
      pause_metadata: null,
      resume_metadata: null,
      completion_metadata: null,
      started_at: null,
      last_checkpoint_at: null,
      created_at: "2026-06-30T00:00:00Z",
      updated_at: "2026-06-30T00:00:00Z",
    });
    launchRunMock.mockResolvedValue({
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
    });
  });

  it("launches a run and shows queued confirmation", async () => {
    const success = vi.fn();
    render(<LaunchRunDialog open={true} onClose={() => {}} onSuccess={success} />);

    await screen.findByText("Initiate project run");
    await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Destination object"), {
      target: { value: "Customer" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Launch run" }));

    await waitFor(() =>
      expect(createRunMock).toHaveBeenCalledWith("token-1", "project-1", {
        destination_object_name: "Customer",
        source_definition_id: "source-1",
        environment: null,
      }),
    );
    await waitFor(() => expect(launchRunMock).toHaveBeenCalledWith("token-1", "project-1", "run-1"));
    expect(await screen.findByText("Run queued")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View run" })).toHaveAttribute(
      "href",
      "/runs/run-1?projectId=project-1",
    );
    expect(success).toHaveBeenCalled();
  });
});
