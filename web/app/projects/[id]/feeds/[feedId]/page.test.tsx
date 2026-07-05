import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FeedDetailPage from "./page";

const {
  loadUiSessionMock,
  getFeedContractMock,
  listFeedSlicesMock,
  listFeedValueSummariesMock,
  getMappingSnapshotMock,
  listLookupValueMapsMock,
  approveFeedSliceMock,
  rejectFeedSliceMock,
  generateLookupSnapshotMock,
  createLookupValueMapMock,
  routerPushMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getFeedContractMock: vi.fn(),
  listFeedSlicesMock: vi.fn(),
  listFeedValueSummariesMock: vi.fn(),
  getMappingSnapshotMock: vi.fn(),
  listLookupValueMapsMock: vi.fn(),
  approveFeedSliceMock: vi.fn(),
  rejectFeedSliceMock: vi.fn(),
  generateLookupSnapshotMock: vi.fn(),
  createLookupValueMapMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock("../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../lib/feeds-api", () => ({
  getFeedContract: getFeedContractMock,
  listFeedSlices: listFeedSlicesMock,
  listFeedValueSummaries: listFeedValueSummariesMock,
  approveFeedSlice: approveFeedSliceMock,
  rejectFeedSlice: rejectFeedSliceMock,
}));

vi.mock("../../../../../lib/mapping-api", () => ({
  getMappingSnapshot: getMappingSnapshotMock,
}));

vi.mock("../../../../../lib/lookup-api", () => ({
  listLookupValueMaps: listLookupValueMapsMock,
  generateLookupSnapshot: generateLookupSnapshotMock,
  createLookupValueMap: createLookupValueMapMock,
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
    listFeedValueSummariesMock.mockResolvedValue([
      {
        summaryId: "sum-1",
        sourceDefinitionId: "feed-1",
        sourceSliceVersion: "v1",
        fieldName: "src_status",
        valueCounts: { A: 10 },
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
    expect(screen.getByRole("button", { name: "Run AI" })).toBeInTheDocument();
    
    fireEvent.click(screen.getByRole("button", { name: "Run AI" }));
    await waitFor(() => {
      expect(generateLookupSnapshotMock).toHaveBeenCalledWith("token-1", "proj-1", "feed-1", { lookupName: "status_map" });
    });
  });
});
