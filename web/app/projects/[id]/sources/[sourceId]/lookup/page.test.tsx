import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import LookupPage from "./page";

const {
  approveLookupSnapshotMock,
  createLookupValueMapMock,
  generateLookupSnapshotMock,
  getSourceContractMock,
  listLookupValueMapsMock,
  listSourceSchemaMock,
  listSourceValueSummariesMock,
  loadUiSessionMock,
  replaceMock,
  topbarMock,
} = vi.hoisted(() => ({
  approveLookupSnapshotMock: vi.fn(),
  createLookupValueMapMock: vi.fn(),
  generateLookupSnapshotMock: vi.fn(),
  getSourceContractMock: vi.fn(),
  listLookupValueMapsMock: vi.fn(),
  listSourceSchemaMock: vi.fn(),
  listSourceValueSummariesMock: vi.fn(),
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

vi.mock("../../../../../../lib/sources-api", () => ({
  getSourceContract: getSourceContractMock,
  listSourceSchema: listSourceSchemaMock,
  listSourceValueSummaries: listSourceValueSummariesMock,
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

    getSourceContractMock.mockResolvedValue({
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
    listSourceSchemaMock.mockResolvedValue([
      {
        name: "status_code",
        inferredType: "text",
        nullable: false,
        maxLength: 32,
      },
    ]);
    listSourceValueSummariesMock.mockResolvedValue([
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
      status: "draft",
      createdAt: "2026-06-30T00:00:00Z",
    });
    generateLookupSnapshotMock.mockResolvedValue({
      lookupSnapshotId: "snapshot-1",
      projectId: "project-1",
      sourceDefinitionId: "source-1",
      lookupName: "status_code",
      lookupSnapshotVersion: "v1",
      valueMap: { A: "ACTIVE", B: "ACTIVE" },
      status: "draft",
      createdAt: "2026-06-30T00:00:00Z",
    });
    approveLookupSnapshotMock.mockResolvedValue({
      lookupSnapshotId: "snapshot-1",
      projectId: "project-1",
      sourceDefinitionId: "source-1",
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
      { lookupName: "status_code", valueMap: { A: "ACTIVE", B: "ACTIVE" } },
    );
    expect(await screen.findByText("Generated snapshot v1.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve snapshot" }));

    await waitFor(() => expect(approveLookupSnapshotMock).toHaveBeenCalledWith(
      "token-1",
      "project-1",
      "source-1",
      "snapshot-1",
    ));
  });
});
