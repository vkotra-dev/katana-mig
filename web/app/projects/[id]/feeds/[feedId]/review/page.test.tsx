import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReviewPage from "./page";

const {
  loadUiSessionMock,
  getAllApprovedMappingSnapshotsMock,
  listLookupValueMapsMock,
  approveMappingSnapshotMock,
  rejectMappingSnapshotMock,
  listFeedSlicesMock,
  listFeedCommentsMock,
  createFeedCommentMock,
  getSignOffStatusMock,
  signBindingMock,
  unsignBindingMock,
  signLookupMock,
  unsignLookupMock,
  pushForReviewMock,
  pokeReviewerMock,
  routerPushMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getAllApprovedMappingSnapshotsMock: vi.fn(),
  listLookupValueMapsMock: vi.fn(),
  approveMappingSnapshotMock: vi.fn(),
  rejectMappingSnapshotMock: vi.fn(),
  listFeedSlicesMock: vi.fn(),
  listFeedCommentsMock: vi.fn(() => Promise.resolve([])),
  createFeedCommentMock: vi.fn(),
  getSignOffStatusMock: vi.fn(() => Promise.resolve({
    complete: false,
    currentBallRole: "central_team",
    bindings: {},
    lookups: {},
  })),
  signBindingMock: vi.fn(),
  unsignBindingMock: vi.fn(),
  signLookupMock: vi.fn(),
  unsignLookupMock: vi.fn(),
  pushForReviewMock: vi.fn(),
  pokeReviewerMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock("../../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../../lib/mapping-api", () => ({
  getAllApprovedMappingSnapshots: getAllApprovedMappingSnapshotsMock,
  approveMappingSnapshot: approveMappingSnapshotMock,
  rejectMappingSnapshot: rejectMappingSnapshotMock,
  patchMappingSnapshot: vi.fn(),
}));

vi.mock("../../../../../../lib/lookup-api", () => ({
  listLookupValueMaps: listLookupValueMapsMock,
}));

vi.mock("../../../../../../lib/feeds-api", () => ({
  listFeedSlices: listFeedSlicesMock,
  listFeedComments: listFeedCommentsMock,
  createFeedComment: createFeedCommentMock,
}));

vi.mock("../../../../../../lib/sign-offs-api", () => ({
  getSignOffStatus: getSignOffStatusMock,
  signBinding: signBindingMock,
  unsignBinding: unsignBindingMock,
  signLookup: signLookupMock,
  unsignLookup: unsignLookupMock,
  pushForReview: pushForReviewMock,
  pokeReviewer: pokeReviewerMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

const BUSINESS_SESSION = {
  accessToken: "token-b",
  expiresAt: "2026-06-30T12:00:00Z",
  role: "project_stakeholder" as const,
  sessionVersion: 1,
  userId: "user-b",
};

const OPERATOR_SESSION = {
  accessToken: "token-o",
  expiresAt: "2026-06-30T12:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-o",
};

const SNAPSHOT = {
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

describe("ReviewPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([SNAPSHOT]);
    listLookupValueMapsMock.mockResolvedValue([]);
    listFeedSlicesMock.mockResolvedValue([]);
    listFeedCommentsMock.mockResolvedValue([]);
    getSignOffStatusMock.mockResolvedValue({
      complete: false,
      currentBallRole: "central_team",
      bindings: {},
      lookups: {},
    });
  });

  async function renderPage() {
    await act(async () => {
      render(<ReviewPage params={Promise.resolve({ id: "proj-1", feedId: "feed-1" })} />);
    });
  }

  it("renders review grid and displays approve/reject controls for project_stakeholder", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);
    approveMappingSnapshotMock.mockResolvedValue({ ...SNAPSHOT, status: "approved" });

    await renderPage();

    expect(await screen.findByText("Review Mappings & Lookups")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => {
      expect(approveMappingSnapshotMock).toHaveBeenCalledWith("token-b", "proj-1", "feed-1");
    });
  });

  it("hides approve/reject controls for operators", async () => {
    loadUiSessionMock.mockReturnValue(OPERATOR_SESSION);

    await renderPage();

    expect(await screen.findByText("Review Mappings & Lookups")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("renders both policy_master and policy_claims tables when multiple snapshots are returned", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([
      {
        ...SNAPSHOT,
        destinationObjectName: "policy_master",
        fieldBindings: [
          { sourceField: "src_id", destinationField: "policy_id", lookupName: null }
        ]
      },
      {
        ...SNAPSHOT,
        destinationObjectName: "policy_claims",
        fieldBindings: [
          { sourceField: "claim_id", destinationField: "id", lookupName: null }
        ]
      }
    ]);

    await renderPage();

    expect(await screen.findByText("policy_master")).toBeInTheDocument();
    expect(screen.getByText("policy_claims")).toBeInTheDocument();
  });

  it("shows draft aggregate status when some are approved and some are draft", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([
      { ...SNAPSHOT, destinationObjectName: "table_1", status: "approved" },
      { ...SNAPSHOT, destinationObjectName: "table_2", status: "draft" }
    ]);
    await renderPage();
    expect(await screen.findByText("draft")).toBeInTheDocument();
  });

  it("shows approved aggregate status when all are approved", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([
      { ...SNAPSHOT, destinationObjectName: "table_1", status: "approved" },
      { ...SNAPSHOT, destinationObjectName: "table_2", status: "approved" }
    ]);
    await renderPage();
    expect(await screen.findByText("approved")).toBeInTheDocument();
  });

  it("shows rejected aggregate status when any is rejected", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([
      { ...SNAPSHOT, destinationObjectName: "table_1", status: "approved" },
      { ...SNAPSHOT, destinationObjectName: "table_2", status: "rejected" }
    ]);
    await renderPage();
    expect(await screen.findByText("rejected")).toBeInTheDocument();
  });

  it("renders decision controls for project_stakeholder when any snapshot is draft", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([
      { ...SNAPSHOT, destinationObjectName: "table_1", status: "approved" },
      { ...SNAPSHOT, destinationObjectName: "table_2", status: "draft" }
    ]);
    await renderPage();
    expect(await screen.findByText("Review Mappings & Lookups")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("hides decision controls for project_stakeholder when all snapshots are approved", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([
      { ...SNAPSHOT, destinationObjectName: "table_1", status: "approved" },
      { ...SNAPSHOT, destinationObjectName: "table_2", status: "approved" }
    ]);
    await renderPage();
    expect(await screen.findByText("Review Mappings & Lookups")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("hides decision controls for central_team even when some snapshots are draft", async () => {
    loadUiSessionMock.mockReturnValue(OPERATOR_SESSION);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([
      { ...SNAPSHOT, destinationObjectName: "table_1", status: "approved" },
      { ...SNAPSHOT, destinationObjectName: "table_2", status: "draft" }
    ]);
    await renderPage();
    expect(await screen.findByText("Review Mappings & Lookups")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("renders sample value chips under source fields when approved slice is present", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-approved",
        sourceDefinitionId: "feed-1",
        sourceSliceVersion: "v1",
        headerCsv: "src_status,other_col",
        rowCount: 10,
        status: "approved",
        approvalRejectionReason: null,
        parseWarnings: null,
        previewRows: ["active,val1", "inactive,val2"],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);

    await renderPage();

    expect(await screen.findByText("Review Mappings & Lookups")).toBeInTheDocument();

    // Expand accordion
    fireEvent.click(screen.getByRole("button", { name: /users/ }));

    // Chips should be present
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
  });

  it("renders unmapped source fields warning panel when columns are unmapped", async () => {
    loadUiSessionMock.mockReturnValue(BUSINESS_SESSION);
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-approved",
        sourceDefinitionId: "feed-1",
        sourceSliceVersion: "v1",
        headerCsv: "src_status,lost_column",
        rowCount: 10,
        status: "approved",
        approvalRejectionReason: null,
        parseWarnings: null,
        previewRows: ["active,unmapped_val"],
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);

    await renderPage();

    expect(await screen.findByText("Review Mappings & Lookups")).toBeInTheDocument();
    expect(screen.getByText(/Unmapped source fields/i)).toBeInTheDocument();
    expect(screen.getByText("lost_column")).toBeInTheDocument();
    expect(screen.getByText("unmapped_val")).toBeInTheDocument();
  });
});
