import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CodegenPage from "./page";

const {
  loadUiSessionMock,
  listFeedContractsMock,
  listCodegenArtifactsMock,
  triggerCodegenMock,
  downloadCodegenDeliveryBundleMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  listFeedContractsMock: vi.fn(),
  listCodegenArtifactsMock: vi.fn(),
  triggerCodegenMock: vi.fn(),
  downloadCodegenDeliveryBundleMock: vi.fn(),
}));

vi.mock("../../../../components/Topbar", () => ({
  Topbar: () => <div>Topbar</div>,
}));

vi.mock("../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../lib/feeds-api", () => ({
  listFeedContracts: listFeedContractsMock,
}));

vi.mock("../../../../lib/codegen-api", () => ({
  listCodegenArtifacts: listCodegenArtifactsMock,
  triggerCodegen: triggerCodegenMock,
  downloadCodegenDeliveryBundle: downloadCodegenDeliveryBundleMock,
}));

describe("CodegenPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    listFeedContractsMock.mockResolvedValue([
      {
        sourceDefinitionId: "source-1",
        projectId: "project-1",
        sourceType: "csv",
        label: "Customer extract",
        encoding: "utf-8",
        destinationObjectReferences: ["Customer"],
        layoutInformation: null,
        copybookText: null,
        status: "active",
        createdAt: "2026-06-30T00:00:00Z",
      },
    ]);
    listCodegenArtifactsMock.mockResolvedValue([
      {
        codegenArtifactId: "cga-1",
        projectId: "project-1",
        destinationObjectName: "Customer",
        runId: null,
        sourceSliceVersion: "v1",
        mappingSnapshotVersion: "v1",
        lookupSnapshotVersion: null,
        sqlBundle: "CREATE TABLE stg_customer (customer_id INT);",
        status: "active",
        createdAt: "2026-06-30T00:00:00Z",
        supersededAt: null,
      },
    ]);
    triggerCodegenMock.mockResolvedValue({
      codegenArtifactId: "cga-2",
      projectId: "project-1",
      destinationObjectName: "Customer",
      status: "active",
      sqlBundlePreview: "CREATE TABLE stg_customer (",
      sourceSliceVersion: "v1",
      mappingSnapshotVersion: "v1",
      lookupSnapshotVersion: null,
      createdAt: "2026-06-30T01:00:00Z",
    });
    downloadCodegenDeliveryBundleMock.mockResolvedValue("-- Customer\n\nCREATE TABLE stg_customer (customer_id INT);");
  });

  it("renders sources and the latest artifact preview", async () => {
    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    expect(await screen.findByText("Customer extract")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate SQL" })).toBeInTheDocument();
    expect(screen.getByText("CREATE TABLE stg_customer (customer_id INT);")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download delivery bundle" })).toBeInTheDocument();
  });

  it("refreshes artifacts after generation", async () => {
    listCodegenArtifactsMock
      .mockResolvedValueOnce([
        {
          codegenArtifactId: "cga-1",
          projectId: "project-1",
          destinationObjectName: "Customer",
          runId: null,
          sourceSliceVersion: "v1",
          mappingSnapshotVersion: "v1",
          lookupSnapshotVersion: null,
          sqlBundle: "CREATE TABLE stg_customer (customer_id INT);",
          status: "active",
          createdAt: "2026-06-30T00:00:00Z",
          supersededAt: null,
        },
      ])
      .mockResolvedValueOnce([
        {
          codegenArtifactId: "cga-2",
          projectId: "project-1",
          destinationObjectName: "Customer",
          runId: null,
          sourceSliceVersion: "v1",
          mappingSnapshotVersion: "v1",
          lookupSnapshotVersion: null,
          sqlBundle: "CREATE TABLE stg_customer_v2 (customer_id INT);",
          status: "active",
          createdAt: "2026-06-30T01:00:00Z",
          supersededAt: null,
        },
      ]);

    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    await screen.findByText("Customer extract");
    fireEvent.click(screen.getByRole("button", { name: "Generate SQL" }));

    await waitFor(() => {
      expect(triggerCodegenMock).toHaveBeenCalledWith("token-1", "project-1", "source-1");
    });
    expect(await screen.findByText("CREATE TABLE stg_customer_v2 (customer_id INT);")).toBeInTheDocument();
  });
});
