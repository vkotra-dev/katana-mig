import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LookupPage from "./page";

const {
  approveLookupSnapshotMock,
  createLookupValueMapMock,
  generateLookupSnapshotMock,
  getFeedContractMock,
  getLatestApprovedMappingSnapshotMock,
  listLookupValueMapsMock,
  listFeedSchemaMock,
  listFeedValueSummariesMock,
  loadUiSessionMock,
  replaceMock,
  topbarMock,
} = vi.hoisted(() => ({
  approveLookupSnapshotMock: vi.fn(),
  createLookupValueMapMock: vi.fn(),
  generateLookupSnapshotMock: vi.fn(),
  getFeedContractMock: vi.fn(),
  getLatestApprovedMappingSnapshotMock: vi.fn(),
  listLookupValueMapsMock: vi.fn(),
  listFeedSchemaMock: vi.fn(),
  listFeedValueSummariesMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
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

vi.mock("../../../../../../lib/feeds-api", () => ({
  getFeedContract: getFeedContractMock,
  listFeedSchema: listFeedSchemaMock,
  listFeedValueSummaries: listFeedValueSummariesMock,
}));

vi.mock("../../../../../../lib/mapping-api", () => ({
  getLatestApprovedMappingSnapshot: getLatestApprovedMappingSnapshotMock,
}));

vi.mock("../../../../../../lib/lookup-api", () => ({
  approveLookupSnapshot: approveLookupSnapshotMock,
  createLookupValueMap: createLookupValueMapMock,
  generateLookupSnapshot: generateLookupSnapshotMock,
  listLookupValueMaps: listLookupValueMapsMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: replaceMock,
  }),
}));

describe("LookupPage", () => {
  it("renders source values and wires the lookup workflow", async () => {
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });

    getFeedContractMock.mockResolvedValue({
      sourceDefinitionId: "source-1",
      projectId: "project-1",
      sourceType: "csv",
      label: "Customer Extract",
      encoding: "utf-8",
      destinationObjectReferences: null,
      layoutInformation: null,
      copybookText: null,
      status: "declared",
      createdAt: "2026-06-30T00:00:00Z",
    });
    getLatestApprovedMappingSnapshotMock.mockResolvedValue({
      mappingSnapshotId: "mapping-1",
      projectId: "project-1",
      destinationObjectName: "Customer",
      mappingSnapshotVersion: "v3",
      fieldBindings: [
        {
          sourceField: "status_code",
          destinationField: "status_id",
          lookupName: "status_code",
        },
      ],
      status: "approved",
      approvedAt: "2026-06-30T00:00:00Z",
      approvedByUserId: "user-1",
      createdAt: "2026-06-30T00:00:00Z",
    });
    listFeedSchemaMock.mockResolvedValue([
      {
        name: "status_code",
        inferredType: "text",
        nullable: false,
        maxLength: 32,
      },
    ]);
    listFeedValueSummariesMock.mockResolvedValue([
      {
        summaryId: "summary-1",
        sourceDefinitionId: "source-1",
        sourceSliceVersion: "v1",
        fieldName: "status_code",
        valueCounts: { A: 4, B: 1 },
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);
    listLookupValueMapsMock.mockResolvedValue([]);
    createLookupValueMapMock.mockResolvedValue({
      lookupValueMapId: "map-1",
      sourceDefinitionId: "source-1",
      lookupName: "status_code",
      destinationTable: [{ id: "ACTIVE", label: "Active" }],
      sourceValueMap: { A: "ACTIVE", B: "ACTIVE" },
      status: "draft",
      createdAt: "2026-06-30T00:00:00Z",
    });
    generateLookupSnapshotMock.mockResolvedValue({
      lookupSnapshotId: "snapshot-1",
      projectId: "project-1",
      lookupName: "status_code",
      lookupSnapshotVersion: "v1",
      valueMap: { A: "ACTIVE", B: "ACTIVE" },
      status: "draft",
      createdAt: "2026-06-30T00:00:00Z",
    });
    approveLookupSnapshotMock.mockResolvedValue({
      lookupSnapshotId: "snapshot-1",
      projectId: "project-1",
      lookupName: "status_code",
      lookupSnapshotVersion: "v1",
      valueMap: { A: "ACTIVE", B: "ACTIVE" },
      status: "approved",
      createdAt: "2026-06-30T00:00:00Z",
    });

    render(<LookupPage params={Promise.resolve({ id: "project-1", sourceId: "source-1" })} />);

    expect(await screen.findByRole("button", { name: "status_code" })).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Lookup name"), {
      target: { value: "status_code" },
    });
    fireEvent.change(screen.getByLabelText("Draft destination table"), {
      target: { value: JSON.stringify([{ id: "ACTIVE", label: "Active" }], null, 2) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply table" }));

    const sourceValueSelects = await screen.findAllByRole("combobox");
    fireEvent.change(sourceValueSelects[0], { target: { value: "ACTIVE" } });
    fireEvent.change(sourceValueSelects[1], { target: { value: "ACTIVE" } });

    fireEvent.click(screen.getByRole("button", { name: "Generate snapshot" }));

    await waitFor(() => expect(createLookupValueMapMock).toHaveBeenCalledTimes(1));
    expect(generateLookupSnapshotMock).toHaveBeenCalledWith(
      "token-1",
      "project-1",
      "source-1",
      { lookupName: "status_code" },
    );
    expect(await screen.findByText("Generated snapshot v1.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve snapshot" }));

    await waitFor(() => expect(approveLookupSnapshotMock).toHaveBeenCalledWith(
      "token-1",
      "project-1",
      "snapshot-1",
    ));
  });

  it("shows lookup errors when save draft fails and accepts destination_id rows", async () => {
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });

    getFeedContractMock.mockResolvedValue({
      sourceDefinitionId: "source-1",
      projectId: "project-1",
      sourceType: "csv",
      label: "Customer Extract",
      encoding: "utf-8",
      destinationObjectReferences: null,
      layoutInformation: null,
      copybookText: null,
      status: "declared",
      createdAt: "2026-06-30T00:00:00Z",
    });
    getLatestApprovedMappingSnapshotMock.mockResolvedValue({
      mappingSnapshotId: "mapping-1",
      projectId: "project-1",
      destinationObjectName: "Customer",
      mappingSnapshotVersion: "v3",
      fieldBindings: [
        {
          sourceField: "status_code",
          destinationField: "status_id",
          lookupName: "status_code",
        },
      ],
      status: "approved",
      approvedAt: "2026-06-30T00:00:00Z",
      approvedByUserId: "user-1",
      createdAt: "2026-06-30T00:00:00Z",
    });
    listFeedSchemaMock.mockResolvedValue([]);
    listFeedValueSummariesMock.mockResolvedValue([
      {
        summaryId: "summary-1",
        sourceDefinitionId: "source-1",
        sourceSliceVersion: "v1",
        fieldName: "status_code",
        valueCounts: { A: 4 },
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);
    listLookupValueMapsMock.mockResolvedValue([]);
    createLookupValueMapMock.mockRejectedValue(new Error("Unable to save lookup draft."));

    render(<LookupPage params={Promise.resolve({ id: "project-1", sourceId: "source-1" })} />);

    const table = await screen.findByLabelText("Draft destination table");
    fireEvent.change(table, {
      target: { value: JSON.stringify([{ destination_id: "ACTIVE", label: "Active" }], null, 2) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply table" }));

    expect(screen.getAllByText("ACTIVE").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));

    await expect(screen.findByRole("alert")).resolves.toHaveTextContent("Unable to save lookup draft.");
  });
});
