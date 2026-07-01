import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MappingPage from "./page";

const {
  approveMappingSnapshotMock,
  getMappingSnapshotMock,
  loadUiSessionMock,
  listFeedSchemaMock,
  patchMappingSnapshotMock,
  proposeMappingSnapshotMock,
  rejectMappingSnapshotMock,
  replaceMock,
  topbarMock,
} = vi.hoisted(() => ({
  approveMappingSnapshotMock: vi.fn(),
  getMappingSnapshotMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
  listFeedSchemaMock: vi.fn(),
  patchMappingSnapshotMock: vi.fn(),
  proposeMappingSnapshotMock: vi.fn(),
  rejectMappingSnapshotMock: vi.fn(),
  replaceMock: vi.fn(),
  topbarMock: vi.fn(),
}));

vi.mock("../../../../../../components/Topbar", () => ({
  Topbar: () => {
    topbarMock();
    return null;
  },
}));

vi.mock("../../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../../lib/mapping-api", () => ({
  approveMappingSnapshot: approveMappingSnapshotMock,
  getMappingSnapshot: getMappingSnapshotMock,
  patchMappingSnapshot: patchMappingSnapshotMock,
  proposeMappingSnapshot: proposeMappingSnapshotMock,
  rejectMappingSnapshot: rejectMappingSnapshotMock,
}));

vi.mock("../../../../../../lib/feeds-api", () => ({
  listFeedSchema: listFeedSchemaMock,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "project-1", sourceId: "source-1" }),
  useRouter: () => ({
    back: replaceMock,
    push: replaceMock,
  }),
}));

const SESSION = {
  accessToken: "token-1",
  expiresAt: "2026-06-30T12:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-1",
};

const DRAFT_SNAPSHOT = {
  mappingSnapshotId: "mapping-1",
  projectId: "project-1",
  destinationObjectName: "Customer",
  mappingSnapshotVersion: "v1",
  fieldBindings: [
    {
      sourceField: "customer_id",
      destinationField: "customer_id",
      lookupName: null,
    },
    {
      sourceField: "full_name",
      destinationField: "full_name",
      lookupName: "name_lookup",
    },
  ],
  status: "draft",
  approvedAt: null,
  approvedByUserId: null,
  createdAt: "2026-06-30T00:00:00Z",
  destinationFields: ["customer_id", "full_name", "email_address"],
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listFeedSchemaMock).mockResolvedValue([
    { name: "customer_id", inferredType: "integer", nullable: false, maxLength: null },
    { name: "full_name", inferredType: "text", nullable: false, maxLength: 200 },
  ]);
});

describe("MappingPage", () => {
  it("shows the no snapshot state and proposes a mapping", async () => {
    vi.mocked(loadUiSessionMock).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshotMock).mockRejectedValue({ code: "mapping_not_found", status: 404 });
    vi.mocked(proposeMappingSnapshotMock).mockResolvedValue({
      ...DRAFT_SNAPSHOT,
      status: "draft",
    });

    render(<MappingPage />);

    expect(await screen.findByText(/no mapping has been proposed yet/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /propose mapping via ai/i }));

    await waitFor(() => {
      expect(proposeMappingSnapshotMock).toHaveBeenCalledWith("token-1", "project-1", "source-1");
    });
  });

  it("renders draft bindings and saves edits", async () => {
    vi.mocked(loadUiSessionMock).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshotMock).mockResolvedValue(DRAFT_SNAPSHOT);
    vi.mocked(patchMappingSnapshotMock).mockResolvedValue({
      ...DRAFT_SNAPSHOT,
      fieldBindings: [
        {
          sourceField: "customer_id",
          destinationField: "email_address",
          lookupName: null,
        },
        {
          sourceField: "full_name",
          destinationField: "full_name",
          lookupName: "name_lookup",
        },
      ],
    });

    render(<MappingPage />);

    expect(await screen.findByRole("combobox", { name: "Destination field for customer_id" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Destination field for customer_id"), {
      target: { value: "email_address" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save draft/i }));

    await waitFor(() => {
      expect(patchMappingSnapshotMock).toHaveBeenCalledWith("token-1", "project-1", "source-1", [
        { sourceField: "customer_id", destinationField: "email_address", lookupName: null },
        { sourceField: "full_name", destinationField: "full_name", lookupName: "name_lookup" },
      ]);
    });
  });

  it("submits an approval decision", async () => {
    vi.mocked(loadUiSessionMock).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshotMock).mockResolvedValue(DRAFT_SNAPSHOT);
    vi.mocked(approveMappingSnapshotMock).mockResolvedValue({
      ...DRAFT_SNAPSHOT,
      status: "approved",
      approvedAt: "2026-06-30T01:00:00Z",
      approvedByUserId: "user-1",
    });
    vi.mocked(rejectMappingSnapshotMock).mockResolvedValue({
      ...DRAFT_SNAPSHOT,
      status: "rejected",
    });

    render(<MappingPage />);

    expect(await screen.findByRole("button", { name: /approve/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /approve/i }));
    fireEvent.click(screen.getByRole("button", { name: /submit decision/i }));

    await waitFor(() => {
      expect(approveMappingSnapshotMock).toHaveBeenCalledWith("token-1", "project-1", "source-1");
    });
  });

  it("submits a rejection decision with a comment", async () => {
    vi.mocked(loadUiSessionMock).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshotMock).mockResolvedValue(DRAFT_SNAPSHOT);
    vi.mocked(rejectMappingSnapshotMock).mockResolvedValue({
      ...DRAFT_SNAPSHOT,
      status: "rejected",
    });

    render(<MappingPage />);

    expect(await screen.findByRole("button", { name: /push back/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /push back/i }));
    fireEvent.change(screen.getByLabelText(/rejection comment/i), {
      target: { value: "Needs another pass." },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit decision/i }));

    await waitFor(() => {
      expect(rejectMappingSnapshotMock).toHaveBeenCalledWith(
        "token-1",
        "project-1",
        "source-1",
        "Needs another pass.",
      );
    });
  });

  it("hides decision controls for auditors", async () => {
    vi.mocked(loadUiSessionMock).mockReturnValue({
      ...SESSION,
      role: "read_only_auditor",
    });
    vi.mocked(getMappingSnapshotMock).mockResolvedValue(DRAFT_SNAPSHOT);

    render(<MappingPage />);

    expect(await screen.findByText(/auditor accounts cannot change the review state/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /push back/i })).not.toBeInTheDocument();
  });

  it("shows settled approved state", async () => {
    vi.mocked(loadUiSessionMock).mockReturnValue(SESSION);
    vi.mocked(getMappingSnapshotMock).mockResolvedValue({
      ...DRAFT_SNAPSHOT,
      status: "approved",
    });

    render(<MappingPage />);

    expect(await screen.findByText(/locked for review/i)).toBeInTheDocument();
  });
});
