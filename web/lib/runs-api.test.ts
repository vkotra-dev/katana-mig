import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createRun,
  getRun,
  launchRun,
  listCheckpoints,
  listRuns,
  resumeRun,
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
