import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CodegenPage from "./page";

const {
  loadUiSessionMock,
  listFeedContractsMock,
  listCodegenArtifactsMock,
  getSchemaAnalysisMock,
  triggerCodegenMock,
  downloadCodegenDeliveryBundleMock,
  triggerSchemaAnalysisMock,
  routerPushMock,
  getProjectMock,
  listFeedFibersMock,
  listFeedSlicesMock,
  getAllApprovedMappingSnapshotsMock,
  getCodegenCodingStandardsTemplateMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  listFeedContractsMock: vi.fn(),
  listCodegenArtifactsMock: vi.fn(),
  getSchemaAnalysisMock: vi.fn(),
  triggerCodegenMock: vi.fn(),
  downloadCodegenDeliveryBundleMock: vi.fn(),
  triggerSchemaAnalysisMock: vi.fn(),
  routerPushMock: vi.fn(),
  getProjectMock: vi.fn(),
  listFeedFibersMock: vi.fn(),
  listFeedSlicesMock: vi.fn(),
  getAllApprovedMappingSnapshotsMock: vi.fn(),
  getCodegenCodingStandardsTemplateMock: vi.fn(),
}));

vi.mock("../../../../components/Topbar", () => ({
  Topbar: () => <div>Topbar</div>,
}));

vi.mock("../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../lib/projects-api", () => ({
  getProject: getProjectMock,
  getCodegenCodingStandardsTemplate: getCodegenCodingStandardsTemplateMock,
}));

vi.mock("../../../../lib/mapping-api", () => ({
  getAllApprovedMappingSnapshots: getAllApprovedMappingSnapshotsMock,
}));

vi.mock("../../../../lib/feeds-api", () => ({
  listFeedContracts: listFeedContractsMock,
  listFeedFibers: listFeedFibersMock,
  listFeedSlices: listFeedSlicesMock,
}));

vi.mock("../../../../lib/codegen-api", () => ({
  listCodegenArtifacts: listCodegenArtifactsMock,
  getSchemaAnalysis: getSchemaAnalysisMock,
  triggerCodegen: triggerCodegenMock,
  downloadCodegenDeliveryBundle: downloadCodegenDeliveryBundleMock,
  triggerSchemaAnalysis: triggerSchemaAnalysisMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPushMock }),
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
    getProjectMock.mockResolvedValue({
      projectId: "project-1",
      name: "Project 1",
      goal: "Goal 1",
      repos: [],
      workspace: null,
      projectResources: null,
      executionEnvironments: [],
      modelPolicy: null,
      canonicalTerms: [],
      constraints: [],
      unresolvedQuestions: [],
      assumptions: [],
      domainConfig: null,
      lexiconScope: null,
      status: "active",
      createdAt: "2026-06-30T00:00:00Z",
      updatedAt: "2026-06-30T00:00:00Z",
      archivedAt: null,
      codegenInstructions: "Date rules",
    });
    getCodegenCodingStandardsTemplateMock.mockResolvedValue("");
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
    getSchemaAnalysisMock.mockResolvedValue({
      analysisId: "analysis-1",
      projectId: "project-1",
      destinationObjectSequence: ["Customer"],
      identifiedCount: 1,
      processedCount: 1,
      analyzedAt: "2026-06-30T00:00:00Z",
    });
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
    triggerSchemaAnalysisMock.mockResolvedValue({
      analysisId: "analysis-2",
      projectId: "project-1",
      destinationObjectSequence: ["Customer"],
      identifiedCount: 1,
      processedCount: 1,
      analyzedAt: "2026-06-30T01:00:00Z",
    });
    listFeedFibersMock.mockResolvedValue([
      {
        fiberId: "fiber-1",
        feedId: "source-1",
        projectId: "project-1",
        fiberType: "lookup",
        fiberKey: "insurance_plan_lkp",
        status: "active",
        proposedMappings: [
          {
            sourceValue: "Gold Plan",
            destEntryId: "entry-1",
            destRow: { plan_id: 1, plan_name: "Gold" },
            confidenceScore: 0.95,
          },
        ],
        fieldBindings: [],
        outputSql: null,
      },
      {
        fiberId: "fiber-2",
        feedId: "source-1",
        projectId: "project-1",
        fiberType: "domain_object",
        fiberKey: "customer",
        status: "active",
        proposedMappings: [],
        fieldBindings: [
          {
            sourceField: "cust_id",
            destinationField: "customer_id",
            lookupName: null,
          },
        ],
        outputSql: null,
      },
    ]);
    listFeedSlicesMock.mockResolvedValue([
      {
        sourceSliceId: "slice-1",
        sourceDefinitionId: "source-1",
        sourceSliceVersion: "v1",
        rowCount: 12000,
        status: "approved",
      },
    ]);
    getAllApprovedMappingSnapshotsMock.mockResolvedValue([
      {
        mappingSnapshotId: "snap-1",
        projectId: "project-1",
        destinationObjectName: "customer",
        mappingSnapshotVersion: "v1",
        fieldBindings: [
          {
            sourceField: "cust_id",
            destinationField: "customer_id",
            lookupName: null,
          },
        ],
        status: "approved",
        approvedAt: "2026-06-30T00:00:00Z",
        approvedByUserId: "user-1",
        createdAt: "2026-06-30T00:00:00Z",
        lookupTableReferences: [],
        destinationFields: ["customer_id"],
        aiTrace: null,
      },
    ]);
  });

  it("renders sources and the latest artifact preview", async () => {
    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    expect(await screen.findByText("Customer extract")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SQL Bundle" })).toHaveClass("bg-primary");
    expect(screen.getByRole("button", { name: "Generate SQL" })).toBeInTheDocument();
    expect(screen.getByText("CREATE TABLE stg_customer (customer_id INT);")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download delivery bundle" })).toBeInTheDocument();
    expect(screen.getByText("Schema dependency analysis")).toBeInTheDocument();
    expect(await screen.findByText("Analyzed: 2026-06-30 00:00")).toBeInTheDocument();
  });

  it("routes back to the project detail page from the overview tab", async () => {
    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    await screen.findByText("Customer extract");
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));

    expect(routerPushMock).toHaveBeenCalledWith("/projects/project-1");
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

  it("reanalyzes the destination schema and refreshes the report panel", async () => {
    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    await screen.findByText("Schema dependency analysis");
    fireEvent.click(screen.getByRole("button", { name: "Re-analyze DDL" }));

    await waitFor(() => {
      expect(triggerSchemaAnalysisMock).toHaveBeenCalledWith("token-1", "project-1");
    });
    expect(await screen.findByText("Schema analysis completed.")).toBeInTheDocument();
  });

  it("suggests coding standards template when clicking Suggest Standards", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    getCodegenCodingStandardsTemplateMock.mockResolvedValue(
      "### Coding Standards and Guidelines\n\n1. **Schemas and Scoping**:\n   - ...\n"
    );

    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    await screen.findByText("Customer extract");

    const textarea = screen.getByPlaceholderText(/e.g. All date columns must use DATE type/i);
    expect(textarea).toHaveValue("Date rules");

    const suggestBtn = screen.getByRole("button", { name: "Suggest Standards" });
    fireEvent.click(suggestBtn);

    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(textarea.value).toContain("Coding Standards and Guidelines");
      expect(textarea.value).toContain("Schemas and Scoping");
    });

    confirmSpy.mockRestore();
  });

  it("generates feed-specific transformation instructions", async () => {
    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    await screen.findByText("Customer extract");

    const toggleBtn = screen.getByText("▶");
    fireEvent.click(toggleBtn);

    const generateBtn = await screen.findByRole("button", { name: "Generate Instructions" });
    fireEvent.click(generateBtn);

    const textarea = screen.getByPlaceholderText(/e.g. Map claim_no -> external_claim_number/i);
    await waitFor(() => {
      expect(textarea.value).toContain("Transformation Specification for Feed:");
      expect(textarea.value).toContain("### 1. Approved Lookup Data");
      expect(textarea.value).toContain('- Approved lookup: "insurance_plan_lkp"');
      expect(textarea.value).toContain('"Gold Plan"');
      expect(textarea.value).toContain("### 2. Approved Destination Mappings");
      expect(textarea.value).toContain('- Destination object: "customer"');
      expect(textarea.value).toContain('Source field "cust_id" -> Destination column "customer_id"');
      expect(textarea.value).toContain("### 4. Unmapped Required Destination Fields");
      expect(textarea.value).toContain("### 5. Source Characteristics");
    });
  });

  it("allows inspecting AI prompt logs", async () => {
    listCodegenArtifactsMock.mockResolvedValue([
      {
        codegenArtifactId: "artifact-1",
        projectId: "project-1",
        destinationObjectName: "customer",
        runId: null,
        sourceSliceVersion: "v1",
        mappingSnapshotVersion: "v1",
        lookupSnapshotVersion: null,
        sqlBundle: "CREATE TABLE stg_customer (customer_id INT);",
        compiledSystemPrompt: "System rules content",
        compiledUserPrompt: "User mapping content",
        rawLlmResponse: '{"staging_ddl": "sql", "lookup_ddl": [], "seed_data": [], "stored_procedures": []}',
        status: "active",
        createdAt: "2026-06-30T01:00:00Z",
        supersededAt: null,
      },
    ]);

    render(<CodegenPage params={Promise.resolve({ id: "project-1" })} />);

    const inspectBtn = await screen.findByRole("button", { name: "Inspect AI Logs" });
    fireEvent.click(inspectBtn);

    expect(await screen.findByRole("button", { name: "Hide AI Logs" })).toBeInTheDocument();
    
    // The AiLogViewer is rendered in a new row, so it should display its loading state or table
    expect(screen.getByText("Call Type")).toBeInTheDocument();
    expect(screen.getByText("Model ID")).toBeInTheDocument();
    
    const hideBtn = screen.getByRole("button", { name: "Hide AI Logs" });
    fireEvent.click(hideBtn);
    expect(screen.queryByText("Call Type")).not.toBeInTheDocument();
  });
});
