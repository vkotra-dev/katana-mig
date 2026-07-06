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

  it("allows central_team to edit destination field and save", async () => {
    listFeedSlicesMock.mockResolvedValue([]);
    const snapshotWithMultipleCols = {
      ...DRAFT_SNAPSHOT,
      destinationFields: ["status_id", "status_desc"]
    };
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([snapshotWithMultipleCols]);

    await renderPage();

    // Expand accordion
    fireEvent.click(screen.getByRole("button", { name: /users\s+\d+\s+fields$/i }));

    // Select should be present
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue("status_id");

    // Change value
    fireEvent.change(select, { target: { value: "status_desc" } });
    expect(select).toHaveValue("status_desc");

    // Save button should be rendered and clickable
    const saveBtn = screen.getByRole("button", { name: "Save" });
    expect(saveBtn).toBeInTheDocument();
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(patchMappingSnapshotMock).toHaveBeenCalledWith(
        "token-1",
        "proj-1",
        "feed-1",
        [
          {
            sourceField: "src_status",
            destinationField: "status_desc",
            lookupName: "status_map",
            bindingType: "lookup_fk",
            referenceTableName: "status_ref",
            destinationTableName: undefined
          }
        ],
        "users"
      );
    });
  });

  it("allows central_team to submit mapping for review", async () => {
    listFeedSlicesMock.mockResolvedValue([]);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([DRAFT_SNAPSHOT]);

    await renderPage();

    const submitBtn = screen.getByRole("button", { name: "Submit for review" });
    expect(submitBtn).toBeInTheDocument();
    fireEvent.click(submitBtn);

    expect(screen.getByText("Mapping submitted for business review.")).toBeInTheDocument();
  });
});
