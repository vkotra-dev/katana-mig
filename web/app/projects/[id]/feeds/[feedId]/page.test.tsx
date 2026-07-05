import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FeedDetailPage from "./page";

const {
  loadUiSessionMock,
  getFeedContractMock,
  listFeedSlicesMock,
  listFeedFibersMock,
  getMappingSnapshotMock,
  listLookupValueMapsMock,
  approveFeedSliceMock,
  rejectFeedSliceMock,
  submitLookupInputsMock,
  routerPushMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getFeedContractMock: vi.fn(),
  listFeedSlicesMock: vi.fn(),
  listFeedFibersMock: vi.fn(),
  getMappingSnapshotMock: vi.fn(),
  listLookupValueMapsMock: vi.fn(),
  approveFeedSliceMock: vi.fn(),
  rejectFeedSliceMock: vi.fn(),
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
  approveFeedSlice: approveFeedSliceMock,
  rejectFeedSlice: rejectFeedSliceMock,
}));

vi.mock("../../../../../lib/mapping-api", () => ({
  getMappingSnapshot: getMappingSnapshotMock,
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
    getMappingSnapshotMock.mockResolvedValue(DRAFT_SNAPSHOT);
    listLookupValueMapsMock.mockResolvedValue([]);
  });

  async function renderPage() {
    await act(async () => {
      render(<FeedDetailPage params={Promise.resolve({ id: "proj-1", feedId: "feed-1" })} />);
    });
  }

  it("shows workspace lock banner when slice is pending", async () => {
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-1",
        sourceDefinitionId: "feed-1",
        sourceSliceVersion: "v1",
        headerCsv: null,
        rowCount: 10,
        status: "pending",
        approvalRejectionReason: null,
        parseWarnings: null,
        previewRows: [],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);

    await renderPage();

    expect(await screen.findByText(/Workspace Locked/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve Slice" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve Slice" }));
    await waitFor(() => {
      expect(approveFeedSliceMock).toHaveBeenCalledWith("token-1", "proj-1", "feed-1", "slice-1");
    });
  });

  it("unlocks downstream mappings and lookup fibers when slice is approved", async () => {
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
        previewRows: [],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);

    await renderPage();

    expect(await screen.findByText("Users Feed")).toBeInTheDocument();
    expect(screen.queryByText(/Workspace Locked/i)).not.toBeInTheDocument();

    expect(screen.getAllByText("status_map")[0]).toBeInTheDocument();
    
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
});
