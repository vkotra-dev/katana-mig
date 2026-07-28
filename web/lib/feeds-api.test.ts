import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveFiber,
  createFeedComment,
  getFeedContract,
  getFiber,
  createFeedContract,
  assignFiber,
  listFeedContracts,
  listFeedComments,
  listFeedValueSummaries,
  listFeedSlices,
  listFeedSchema,
  triggerFiber,
  uploadFeedCopybook,
  uploadFeedSlice,
  type FeedCommentRecord,
  type FeedContractRecord,
  type FiberRecord,
  type FeedSliceRecord,
} from "./feeds-api";

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
  mapping_ownership_warnings: null,
};

const contract: FeedContractRecord = {
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
  mappingStatus: null,
  mappingOwnershipWarnings: null,
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
  preview_rows: ["100042,***"],
  created_at: "2026-06-30T00:00:00Z",
};

const slice: FeedSliceRecord = {
  sourceSliceId: "slice-1",
  sourceDefinitionId: "source-1",
  sourceSliceVersion: "v1",
  headerCsv: "CUST_ID,SURNAME",
  rowCount: 1,
  status: "pending_approval",
  approvalRejectionReason: null,
  parseWarnings: [],
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

const fiberResponse = {
  fiber_id: "fiber-1",
  feed_id: "feed-1",
  project_id: "project-1",
  fiber_type: "domain_object",
  fiber_key: "customer",
  status: "mapped",
  source: "auto",
  proposed_mappings: [
    {
      source_value: "A",
      dest_entry_id: "entry-1",
      dest_row: { code: "A", label: "Active" },
      confidence_score: 0.91,
    },
  ],
  field_bindings: [
    {
      source_field: "cust_id",
      destination_field: "customer_id",
      lookup_name: null,
    },
  ],
  output_sql: null,
  created_at: "2026-06-30T00:00:00Z",
  updated_at: "2026-06-30T00:00:00Z",
};

const fiberRecord: FiberRecord = {
  fiberId: "fiber-1",
  feedId: "feed-1",
  projectId: "project-1",
  fiberType: "domain_object",
  fiberKey: "customer",
  status: "mapped",
  source: "auto",
  proposedMappings: [
    {
      sourceValue: "A",
      destEntryId: "entry-1",
      destRow: { code: "A", label: "Active" },
      confidenceScore: 0.91,
    },
  ],
  fieldBindings: [
    {
      sourceField: "cust_id",
      destinationField: "customer_id",
      lookupName: null,
    },
  ],
  outputSql: null,
  createdAt: "2026-06-30T00:00:00Z",
  updatedAt: "2026-06-30T00:00:00Z",
};

const commentResponse = {
  comment_id: "comment-1",
  feed_id: "feed-1",
  user_id: "user-1",
  display_name: "Janet Smith",
  role: "project_stakeholder",
  body: "ACCT_TYPE value RETD should map to Retired.",
  created_at: "2026-07-01T10:00:00Z",
};

const comment: FeedCommentRecord = {
  commentId: "comment-1",
  feedId: "feed-1",
  userId: "user-1",
  displayName: "Janet Smith",
  role: "project_stakeholder",
  body: "ACCT_TYPE value RETD should map to Retired.",
  createdAt: "2026-07-01T10:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("feeds-api", () => {
  it("lists feed contracts", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [contractResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listFeedContracts("token-1", "project-1");

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

  it("creates a feed contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => contractResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createFeedContract("token-1", "project-1", {
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

    const result = await uploadFeedCopybook("token-1", "project-1", "source-1", {
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

  it("uploads a feed slice", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => sliceResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await uploadFeedSlice("token-1", "project-1", "source-1", {
      content: "csv text",
    });

    expect(result.sourceSliceId).toBe("slice-1");
  });

  it("lists feed slices", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [sliceResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listFeedSlices("token-1", "project-1", "source-1");

    expect(result[0]).toMatchObject(slice);
  });

  it("fetches a single feed contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => contractResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getFeedContract("token-1", "project-1", "source-1");

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

  it("lists feed schema columns", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => schemaResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listFeedSchema("token-1", "project-1", "source-1");

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

  it("lists feed value summaries with an optional field filter", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => valueSummaryResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listFeedValueSummaries("token-1", "project-1", "source-1", "status_code");

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

  it("fetches a single fiber", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => fiberResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getFiber("token-1", "project-1", "feed-1", "fiber-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/feeds/feed-1/fibers/fiber-1`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result).toMatchObject(fiberRecord);
  });

  it("assigns a fiber with an empty JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => fiberResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await assignFiber("token-1", "project-1", "feed-1", "fiber-1");

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({});
    expect(result.status).toBe("mapped");
  });

  it("approves a fiber with an empty JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => fiberResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await approveFiber("token-1", "project-1", "feed-1", "fiber-1");

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({});
    expect(result.fiberId).toBe("fiber-1");
  });

  it("triggers a fiber with an empty JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => fiberResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await triggerFiber("token-1", "project-1", "feed-1", "fiber-1");

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({});
    expect(result.projectId).toBe("project-1");
  });
});

describe("feeds-api comment helpers", () => {
  it("listFeedComments fetches and maps comments", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [commentResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listFeedComments("token-1", "project-1", "feed-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/feeds/feed-1/comments`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject(comment);
  });

  it("createFeedComment posts body and returns mapped comment", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => commentResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createFeedComment(
      "token-1",
      "project-1",
      "feed-1",
      "ACCT_TYPE value RETD should map to Retired.",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/feeds/feed-1/comments`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          body: "ACCT_TYPE value RETD should map to Retired.",
        }),
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result).toMatchObject(comment);
  });

  it("listFeedComments throws FeedApiError on non-ok response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ error: { code: "forbidden", message: "No access" } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(listFeedComments("bad-token", "project-1", "feed-1")).rejects.toThrow("No access");
  });
});
