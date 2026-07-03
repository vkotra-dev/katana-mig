import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveDryRun,
  createRun,
  getDryRunArtifact,
  getRun,
  launchRun,
  listKnowledgeFreezes,
  listCheckpoints,
  listRuns,
  pushBackDryRun,
  resumeRun,
  type DryRunArtifactRecord,
  type KnowledgeFreezeRecord,
  type RunCheckpoint,
  type RunRecord,
} from "./runs-api";

const BASE = "http://127.0.0.1:8000";
const TOKEN = "test-token";
const PROJECT_ID = "proj-1";
const RUN_ID = "run-1";

const stub: RunRecord = {
  run_id: RUN_ID,
  project_id: PROJECT_ID,
  destination_object_name: "Customer",
  source_definition_reference: "source-1",
  environment: null,
  status: "queued",
  current_stage: null,
  source_slice_version: null,
  mapping_snapshot_version: null,
  lookup_snapshot_version: null,
  lookup_snapshot_versions: null,
  code_generation_input_snapshot_version: null,
  codegen_artifact_id: null,
  knowledge_freeze_version: null,
  start_metadata: null,
  pause_metadata: null,
  resume_metadata: null,
  completion_metadata: null,
  started_at: null,
  last_checkpoint_at: null,
  created_at: "2026-06-29T00:00:00Z",
  updated_at: "2026-06-29T00:00:00Z",
};

const checkpointResponse = {
  run_checkpoint_id: "checkpoint-1",
  run_id: RUN_ID,
  current_stage: "mapping",
  current_object: "Customer",
  current_environment: "dev",
  approved_snapshots: {
    source_slice_version: "v1",
    lookup_snapshot_versions: {
      status_map: "v1",
    },
  },
  last_completed_row: 499,
  pause_reason: null,
  created_at: "2026-06-29T00:10:00Z",
};

const checkpoint: RunCheckpoint = {
  checkpoint_id: "checkpoint-1",
  run_id: RUN_ID,
  stage: "mapping",
  current_object: "Customer",
  current_environment: "dev",
  approved_snapshots: {
    source_slice_version: "v1",
    lookup_snapshot_versions: {
      status_map: "v1",
    },
  },
  last_completed_row: 499,
  pause_reason: null,
  created_at: "2026-06-29T00:10:00Z",
};

const freezeRecord: KnowledgeFreezeRecord = {
  run_id: RUN_ID,
  knowledge_freeze_version: "cga-123",
  destination_object_name: "Customer",
  environment: "prod",
  status: "completed",
  started_at: "2026-07-01T10:00:00Z",
  created_at: "2026-07-01T10:05:00Z",
};

const dryRunArtifactResponse = {
  dry_run_artifact_id: "dra-1",
  run_id: RUN_ID,
  project_id: PROJECT_ID,
  destination_object_name: "customers",
  success_count: 1840,
  failure_count: 2,
  field_coverage_pct: 94.3,
  pii_fields: [{ field: "SURNAME", token: "EMAIL_XXXX" }],
  sample_rows: [{ source: { CUST_ID: "100042" }, mapped: { customer_id: "100042" } }],
  failures: [{ row_index: 141, reason: "unmapped_lookup", field: "ACCT_TYPE", value: "RETD" }],
  push_back_comment: null,
  status: "pending",
  created_at: "2026-07-01T00:00:00Z",
};

const dryRunArtifact: DryRunArtifactRecord = {
  dryRunArtifactId: "dra-1",
  runId: RUN_ID,
  projectId: PROJECT_ID,
  destinationObjectName: "customers",
  successCount: 1840,
  failureCount: 2,
  fieldCoveragePct: 94.3,
  piiFields: [{ field: "SURNAME", token: "EMAIL_XXXX" }],
  sampleRows: [{ source: { CUST_ID: "100042" }, mapped: { customer_id: "100042" } }],
  failures: [{ rowIndex: 141, reason: "unmapped_lookup", field: "ACCT_TYPE", value: "RETD" }],
  pushBackComment: null,
  status: "pending",
  createdAt: "2026-07-01T00:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("listRuns", () => {
  it("GETs /projects/{id}/runs", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [stub],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listRuns(TOKEN, PROJECT_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/runs`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      }),
    );
    expect(result).toHaveLength(1);
    expect(result[0].run_id).toBe(RUN_ID);
  });
});

describe("listKnowledgeFreezes", () => {
  it("GETs /projects/{id}/knowledge-freezes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [freezeRecord],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listKnowledgeFreezes(TOKEN, PROJECT_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/knowledge-freezes`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      }),
    );
    expect(result).toHaveLength(1);
    expect(result[0].knowledge_freeze_version).toBe("cga-123");
  });
});

describe("getRun", () => {
  it("GETs /projects/{id}/runs/{run_id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => stub,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getRun(TOKEN, PROJECT_ID, RUN_ID);
    expect(result.run_id).toBe(RUN_ID);
  });
});

describe("createRun", () => {
  it("POSTs run creation", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => stub,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createRun(TOKEN, PROJECT_ID, {
      destination_object_name: "Customer",
      source_definition_id: "source-1",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/runs`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      }),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      destination_object_name: "Customer",
      source_definition_id: "source-1",
      environment: null,
    });
    expect(result.status).toBe("queued");
  });
});

describe("launchRun", () => {
  it("POSTs to /launch", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...stub, status: "completed" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await launchRun(TOKEN, PROJECT_ID, RUN_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/runs/${RUN_ID}/launch`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.status).toBe("completed");
  });
});

describe("resumeRun", () => {
  it("POSTs to /resume", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...stub, status: "running" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await resumeRun(TOKEN, PROJECT_ID, RUN_ID);
    expect(result.status).toBe("running");
  });
});

describe("listCheckpoints", () => {
  it("maps checkpoint field names", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [checkpointResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listCheckpoints(TOKEN, PROJECT_ID, RUN_ID);
    expect(result).toEqual([checkpoint]);
  });
});

describe("getDryRunArtifact", () => {
  it("GETs /projects/{id}/runs/{run_id}/dry-run", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => dryRunArtifactResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getDryRunArtifact(TOKEN, PROJECT_ID, RUN_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/runs/${RUN_ID}/dry-run`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      }),
    );
    expect(result).toEqual(dryRunArtifact);
  });

  it("throws RunApiError on 404", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ error: { code: "dry_run_artifact_not_found", message: "Not found." } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getDryRunArtifact(TOKEN, PROJECT_ID, RUN_ID)).rejects.toMatchObject({
      code: "dry_run_artifact_not_found",
      status: 404,
    });
  });
});

describe("approveDryRun", () => {
  it("POSTs to /dry-run/approve and returns RunRecord", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...stub, status: "queued" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await approveDryRun(TOKEN, PROJECT_ID, RUN_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/runs/${RUN_ID}/dry-run/approve`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.status).toBe("queued");
  });
});

describe("pushBackDryRun", () => {
  it("POSTs to /dry-run/push-back with comment body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...stub, status: "dry_run_review" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await pushBackDryRun(TOKEN, PROJECT_ID, RUN_ID, "Row 142 is wrong.");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/runs/${RUN_ID}/dry-run/push-back`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      }),
    );
    const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
    const body = JSON.parse(String(requestInit?.body ?? "{}")) as {
      comment: string;
    };
    expect(body.comment).toBe("Row 142 is wrong.");
    expect(result.status).toBe("dry_run_review");
  });
});
