import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FeedDetailPage from "./page";

const {
  loadUiSessionMock,
  getFeedContractMock,
  listFeedSlicesMock,
  listFeedFibersMock,
  listFeedSchemaMock,
  analyzeFeedSourceMock,
  patchFeedMappingHintsMock,
  uploadFeedSliceMock,
  getAllApprovedMappingSnapshotsMock,
  proposeMappingSnapshotMock,
  patchMappingSnapshotMock,
  listLookupValueMapsMock,
  submitLookupInputsMock,
  routerPushMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getFeedContractMock: vi.fn(),
  listFeedSlicesMock: vi.fn(),
  listFeedFibersMock: vi.fn(),
  listFeedSchemaMock: vi.fn(),
  analyzeFeedSourceMock: vi.fn(),
  patchFeedMappingHintsMock: vi.fn(),
  uploadFeedSliceMock: vi.fn(),
  getLookupSourceEntriesMock: vi.fn(() => Promise.resolve([])),
  getLookupDestEntriesMock: vi.fn(() => Promise.resolve([])),
  getAllApprovedMappingSnapshotsMock: vi.fn(),
  proposeMappingSnapshotMock: vi.fn(),
  patchMappingSnapshotMock: vi.fn(),
  listLookupValueMapsMock: vi.fn(),
  submitLookupInputsMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock("../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../lib/feeds-api", () => ({
  getFeedContract: getFeedContractMock,
  listFeedSlices: listFeedSlicesMock,
  listFeedFibers: listFeedFibersMock,
  listFeedSchema: listFeedSchemaMock,
  analyzeFeedSource: analyzeFeedSourceMock,
  patchFeedMappingHints: patchFeedMappingHintsMock,
  uploadFeedSlice: uploadFeedSliceMock,
}));

vi.mock("../../../../../lib/feed-slice-comments-api", () => ({
  listFeedSliceComments: vi.fn(() => Promise.resolve([])),
  createFeedSliceComment: vi.fn(),
}));

vi.mock("../../../../../lib/mapping-api", () => ({
  getAllApprovedMappingSnapshots: getAllApprovedMappingSnapshotsMock,
  proposeMappingSnapshot: proposeMappingSnapshotMock,
  patchMappingSnapshot: patchMappingSnapshotMock,
}));

vi.mock("../../../../../lib/lookup-api", () => ({
  listLookupValueMaps: listLookupValueMapsMock,
  submitLookupInputs: submitLookupInputsMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

const SESSION = {
  accessToken: "token-1",
  expiresAt: "2026-06-30T12:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-1",
};

const FEED = {
  sourceDefinitionId: "feed-1",
  projectId: "proj-1",
  sourceType: "csv" as const,
  label: "Users Feed",
  encoding: "utf-8",
  destinationObjectReferences: null,
  layoutInformation: null,
  copybookText: null,
  status: "active",
  createdAt: "2026-06-30T00:00:00Z",
};

const DRAFT_SNAPSHOT = {
  mappingSnapshotId: "mapping-1",
  projectId: "proj-1",
  destinationObjectName: "users",
  mappingSnapshotVersion: "v1",
  fieldBindings: [
    {
      sourceField: "src_status",
      destinationField: "status_id",
      lookupName: "status_map",
      bindingType: "lookup_fk",
      referenceTableName: "status_ref",
    },
  ],
  status: "draft",
  approvedAt: null,
  approvedByUserId: null,
  createdAt: "2026-06-30T00:00:00Z",
  destinationFields: ["status_id"],
  lookupTableReferences: [
    { lookupName: "status_map", destinationTableName: "status_ref" },
  ],
};

describe("FeedDetailPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    loadUiSessionMock.mockReturnValue(SESSION);
    getFeedContractMock.mockResolvedValue(FEED);
    listFeedFibersMock.mockResolvedValue([
      {
        fiberId: "fib-status",
        feedId: "feed-1",
        projectId: "proj-1",
        fiberType: "lookup",
        fiberKey: "status_map",
        status: "deferred",
        source: "auto",
        proposedMappings: null,
        fieldBindings: null,
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([DRAFT_SNAPSHOT]);
    listLookupValueMapsMock.mockResolvedValue([]);
    listFeedSchemaMock.mockResolvedValue([{ fieldName: "src_status" }]);
  });

  async function renderPage() {
    await act(async () => {
      render(<FeedDetailPage params={Promise.resolve({ id: "proj-1", feedId: "feed-1" })} />);
    });
  }

  it("renders preview rows and allows triggering AI analysis", async () => {
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-1",
        sourceDefinitionId: "feed-1",
        sourceSliceVersion: "v1",
        headerCsv: null,
        rowCount: 10,
        status: "approved",
        approvalRejectionReason: null,
        parseWarnings: null,
        previewRows: ["A"],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);

    await renderPage();

    expect(await screen.findByText("Slice")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();

    // Expand the "users" table accordion
    fireEvent.click(screen.getByRole("button", { name: /users\s+\d+\s+fields$/i }));

    await waitFor(() => {
      expect(screen.getAllByText("src_status")[0]).toBeInTheDocument();
    });

    const analyzeBtn = screen.getByRole("button", { name: "Analyze with AI" });
    fireEvent.click(analyzeBtn);

    await waitFor(() => {
      expect(proposeMappingSnapshotMock).toHaveBeenCalledWith("token-1", "proj-1", "feed-1");
    });
  });

  it("allows submitting lookup inputs", async () => {
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-1",
        sourceDefinitionId: "feed-1",
        sourceSliceVersion: "v1",
        headerCsv: null,
        rowCount: 10,
        status: "approved",
        approvalRejectionReason: null,
        parseWarnings: null,
        previewRows: ["A"],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);

    await renderPage();

    expect(screen.getAllByText("status_map")[0]).toBeInTheDocument();
    
    // Expand the "status_map" lookup accordion
    fireEvent.click(screen.getAllByText("status_map")[0]);
    
    // Fill in textareas
    fireEvent.change(screen.getByPlaceholderText(/VALUE_A/i), { target: { value: "A\nB" } });
    fireEvent.change(screen.getByPlaceholderText(/id,description/i), { target: { value: "id,description\nA,Active\nB,Inactive" } });

    const btn = screen.getByRole("button", { name: "AI Analyze" });
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn);

    await waitFor(() => {
      expect(submitLookupInputsMock).toHaveBeenCalledWith("token-1", "proj-1", "feed-1", "fib-status", {
        sourceValues: ["A", "B"],
        destinationLookupCsv: "id,description\nA,Active\nB,Inactive",
      });
    });
  });

  it("renders destination field as plain text and is read-only", async () => {
    listFeedSlicesMock.mockResolvedValue([]);
    const snapshotWithMultipleCols = {
      ...DRAFT_SNAPSHOT,
      destinationFields: ["status_id", "status_desc"]
    };
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([snapshotWithMultipleCols]);

    await renderPage();

    // Expand accordion
    fireEvent.click(screen.getByRole("button", { name: /users\s+\d+\s+fields$/i }));

    // Select should not be present
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    // Destination field text should be present
    expect(screen.getByText("status_id")).toBeInTheDocument();
    // Save button should not be present
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
  });

  it("renders 'Go to review page' button when mapping snapshots exist", async () => {
    listFeedSlicesMock.mockResolvedValue([]);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([DRAFT_SNAPSHOT]);

    await renderPage();

    const reviewBtn = screen.getByRole("button", { name: "Go to review page" });
    expect(reviewBtn).toBeInTheDocument();
    fireEvent.click(reviewBtn);

    expect(routerPushMock).toHaveBeenCalledWith("/projects/proj-1/feeds/feed-1/review");
  });

  it("allows central_team to edit and save mapping hints", async () => {
    listFeedSlicesMock.mockResolvedValue([]);
    patchFeedMappingHintsMock.mockResolvedValue({ ...FEED, mappingHints: "new-hints" });

    await renderPage();

    const textarea = screen.getByLabelText("AI Mapping Hints");
    expect(textarea).toBeInTheDocument();
    fireEvent.change(textarea, { target: { value: "some operator hints" } });

    const saveHintsBtn = screen.getByRole("button", { name: "Save Hints" });
    fireEvent.click(saveHintsBtn);

    await waitFor(() => {
      expect(patchFeedMappingHintsMock).toHaveBeenCalledWith(
        "token-1",
        "proj-1",
        "feed-1",
        "some operator hints"
      );
    });
  });

  it("renders AI Trace details inside details element when trace is present", async () => {
    listFeedSlicesMock.mockResolvedValue([]);
    const snapshotWithTrace = {
      ...DRAFT_SNAPSHOT,
      aiTrace: {
        model_id: "gemini-2.5",
        system_prompt: "sys-instruction",
        user_prompt: "user-input",
        raw_response: { tables: [] },
      },
    };
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([snapshotWithTrace]);

    await renderPage();

    // Project AI Trace is always rendered for admin/central_team at the bottom
    expect(screen.getByText("Project AI Trace & Reasoning")).toBeInTheDocument();
    
    // Check that the AiLogViewer table headers appear (indicating it rendered)
    expect(screen.getByText("Call Type")).toBeInTheDocument();
    expect(screen.getByText("Model ID")).toBeInTheDocument();
    expect(screen.getByText("Timestamp")).toBeInTheDocument();
  });

  it("renders pending approval banner when latest slice is pending_approval", async () => {
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-pending",
        sourceDefinitionId: "feed-1",
        sourceSliceVersion: "v1",
        headerCsv: null,
        rowCount: 10,
        status: "pending_approval",
        approvalRejectionReason: null,
        parseWarnings: null,
        previewRows: [],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);

    await renderPage();

    expect(screen.getByText(/Source data is pending approval/i)).toBeInTheDocument();
    expect(screen.getByText("pending approval")).toBeInTheDocument();
  });

  it("renders rejection banner with upload replacement form when latest slice is rejected", async () => {
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-rejected",
        sourceDefinitionId: "feed-1",
        sourceSliceVersion: "v1",
        headerCsv: null,
        rowCount: 10,
        status: "rejected",
        approvalRejectionReason: "Columns do not match target schema",
        parseWarnings: null,
        previewRows: [],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);

    await renderPage();

    expect(screen.getByText(/Source data was rejected: Columns do not match target schema/i)).toBeInTheDocument();
    expect(screen.getByText("rejected")).toBeInTheDocument();

    const uploadBtn = screen.getByRole("button", { name: "Upload replacement" });
    expect(uploadBtn).toBeInTheDocument();
    expect(uploadBtn).toBeDisabled();
  });

  it("renders quiet replacement upload control when latest slice is approved", async () => {
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-approved",
        sourceDefinitionId: "feed-1",
        sourceSliceVersion: "v1",
        headerCsv: null,
        rowCount: 10,
        status: "approved",
        approvalRejectionReason: null,
        parseWarnings: null,
        previewRows: [],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);

    await renderPage();

    expect(screen.getByText(/Upload a corrected file to replace this slice/i)).toBeInTheDocument();
    expect(screen.getByText("approved")).toBeInTheDocument();
    const uploadBtn = screen.getByRole("button", { name: "Upload new slice" });
    expect(uploadBtn).toBeInTheDocument();
    expect(uploadBtn).toBeDisabled();
  });
});
