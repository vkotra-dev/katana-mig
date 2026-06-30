import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getSourceContract,
  createSourceContract,
  listSourceContracts,
  listSourceValueSummaries,
  listSourceSlices,
  listSourceSchema,
  uploadSourceCopybook,
  uploadSourceSlice,
  type SourceContractRecord,
  type SourceSliceRecord,
} from "./sources-api";

const BASE = "http://127.0.0.1:8000";

const contractResponse = {
  source_definition_id: "source-1",
  project_id: "project-1",
  source_type: "csv",
  label: "Customer Extract",
  encoding: "utf-8",
  destination_object_references: ["Customer"],
  layout_information: null,
  copybook_text: null,
  status: "declared",
  created_at: "2026-06-30T00:00:00Z",
};

const contract: SourceContractRecord = {
  sourceDefinitionId: "source-1",
  projectId: "project-1",
  sourceType: "csv",
  label: "Customer Extract",
  encoding: "utf-8",
  destinationObjectReferences: ["Customer"],
  layoutInformation: null,
  copybookText: null,
  status: "declared",
  createdAt: "2026-06-30T00:00:00Z",
};

const sliceResponse = {
  source_slice_id: "slice-1",
  source_definition_id: "source-1",
  source_slice_version: "v1",
  header_csv: "CUST_ID,SURNAME",
  row_count: 1,
  status: "pending_approval",
  approval_rejection_reason: null,
  parse_warnings: [],
  file_storage_path: "/tmp/source.csv",
  preview_rows: ["100042,***"],
  created_at: "2026-06-30T00:00:00Z",
};

const slice: SourceSliceRecord = {
  sourceSliceId: "slice-1",
  sourceDefinitionId: "source-1",
  sourceSliceVersion: "v1",
  headerCsv: "CUST_ID,SURNAME",
  rowCount: 1,
  status: "pending_approval",
  approvalRejectionReason: null,
  parseWarnings: [],
  fileStoragePath: "/tmp/source.csv",
  previewRows: ["100042,***"],
  createdAt: "2026-06-30T00:00:00Z",
};

const schemaResponse = [
  {
    name: "status_code",
    inferred_type: "text",
    nullable: false,
    max_length: 32,
  },
];

const valueSummaryResponse = [
  {
    summary_id: "summary-1",
    source_definition_id: "source-1",
    source_slice_version: "v1",
    field_name: "status_code",
    value_counts: { A: 4, B: 1 },
    created_at: "2026-06-30T00:00:00Z",
  },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("sources-api", () => {
  it("lists source contracts", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [contractResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listSourceContracts("token-1", "project-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result[0].sourceDefinitionId).toBe("source-1");
  });

  it("creates a source contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => contractResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createSourceContract("token-1", "project-1", {
      sourceType: "csv",
      label: "Customer Extract",
      encoding: "utf-8",
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      source_type: "csv",
      label: "Customer Extract",
      encoding: "utf-8",
    });
    expect(result.projectId).toBe("project-1");
  });

  it("uploads copybook text as JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => contractResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await uploadSourceCopybook("token-1", "project-1", "source-1", {
      content: "copybook text",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/copybook`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ content: "copybook text" }),
      }),
    );
    expect(result.status).toBe("declared");
  });

  it("uploads a source slice", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => sliceResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await uploadSourceSlice("token-1", "project-1", "source-1", {
      content: "csv text",
    });

    expect(result.sourceSliceId).toBe("slice-1");
  });

  it("lists source slices", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [sliceResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listSourceSlices("token-1", "project-1", "source-1");

    expect(result[0]).toMatchObject(slice);
  });

  it("fetches a single source contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => contractResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getSourceContract("token-1", "project-1", "source-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result.sourceDefinitionId).toBe("source-1");
  });

  it("lists source schema columns", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => schemaResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listSourceSchema("token-1", "project-1", "source-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/schema`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result[0].name).toBe("status_code");
  });

  it("lists source value summaries with an optional field filter", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => valueSummaryResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listSourceValueSummaries("token-1", "project-1", "source-1", "status_code");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/value-summary?field=status_code`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result[0].fieldName).toBe("status_code");
  });
});
