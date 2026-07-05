import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReviewPage from "./page";

const {
  loadUiSessionMock,
  getMappingSnapshotMock,
  listLookupValueMapsMock,
  approveMappingSnapshotMock,
  rejectMappingSnapshotMock,
  routerPushMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getMappingSnapshotMock: vi.fn(),
  listLookupValueMapsMock: vi.fn(),
  approveMappingSnapshotMock: vi.fn(),
  rejectMappingSnapshotMock: vi.fn(),
  routerPushMock: vi.fn(),
}));

vi.mock("../../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../../lib/mapping-api", () => ({
  getMappingSnapshot: getMappingSnapshotMock,
  approveMappingSnapshot: approveMappingSnapshotMock,
  rejectMappingSnapshot: rejectMappingSnapshotMock,
}));

vi.mock("../../../../../../lib/lookup-api", () => ({
  listLookupValueMaps: listLookupValueMapsMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

const BUSINESS_SESSION = {
  accessToken: "token-b",
  expiresAt: "2026-06-30T12:00:00Z",
  role: "business_user" as const,
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
    getMappingSnapshotMock.mockResolvedValue(SNAPSHOT);
    listLookupValueMapsMock.mockResolvedValue([]);
  });

  async function renderPage() {
    await act(async () => {
      render(<ReviewPage params={Promise.resolve({ id: "proj-1", feedId: "feed-1" })} />);
    });
  }

  it("renders review grid and displays approve/reject controls for business_user", async () => {
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
});
