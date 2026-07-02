import { afterEach, describe, expect, it, vi } from "vitest";
import { acknowledgeImpact, getImpactReport, type ImpactReport } from "./runs-api";

const BASE = "http://127.0.0.1:8000";
const TOKEN = "test-token";
const PROJECT_ID = "proj-1";
const RUN_ID = "run-1";

const STUB_IMPACT_REPORT: ImpactReport = {
  runId: RUN_ID,
  gateRejection: {
    rejectedBy: "user-99",
    rejectedAt: "2026-07-01T10:00:00Z",
    affectedObjects: ["customers", "orders"],
    requiredChanges: "ACCT_TYPE lookup missing RETD. Remove LEGACY_CODE binding.",
    notes: null,
  },
  replayScope: ["run-abc", "run-def"],
  aiRecommendation: {
    recommendation: "Add RETD to account_type lookup and remove LEGACY_CODE from field bindings.",
    suggestedFix: "1. Open account_type lookup fiber and add RETD. 2. Remove LEGACY_CODE binding.",
    minimalReplayScope: ["customers"],
  },
};

const RAW_IMPACT_RESPONSE = {
  run_id: RUN_ID,
  gate_rejection: {
    rejected_by: "user-99",
    rejected_at: "2026-07-01T10:00:00Z",
    affected_objects: ["customers", "orders"],
    required_changes: "ACCT_TYPE lookup missing RETD. Remove LEGACY_CODE binding.",
    notes: null,
  },
  replay_scope: ["run-abc", "run-def"],
  ai_recommendation: {
    recommendation: "Add RETD to account_type lookup and remove LEGACY_CODE from field bindings.",
    suggested_fix: "1. Open account_type lookup fiber and add RETD. 2. Remove LEGACY_CODE binding.",
    minimal_replay_scope: ["customers"],
  },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("getImpactReport", () => {
  it("GETs /projects/{id}/runs/{run_id}/impact and maps snake_case to camelCase", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => RAW_IMPACT_RESPONSE,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getImpactReport(TOKEN, PROJECT_ID, RUN_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/runs/${RUN_ID}/impact`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      }),
    );
    expect(result).toEqual(STUB_IMPACT_REPORT);
  });

  it("throws RunApiError on 404", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ error: { code: "gate_1_not_rejected", message: "Gate 1 has not been rejected." } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getImpactReport(TOKEN, PROJECT_ID, RUN_ID)).rejects.toMatchObject({
      code: "gate_1_not_rejected",
      status: 404,
    });
  });
});

describe("acknowledgeImpact", () => {
  it("POSTs /projects/{id}/runs/{run_id}/impact/acknowledge and returns RunRecord", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        run_id: RUN_ID,
        project_id: PROJECT_ID,
        destination_object_name: "customers",
        source_definition_reference: null,
        environment: null,
        status: "pending_gate_1",
        current_stage: null,
        source_slice_version: null,
        mapping_snapshot_version: "v1",
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
        created_at: "2026-07-01T00:00:00Z",
        updated_at: "2026-07-01T10:05:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await acknowledgeImpact(TOKEN, PROJECT_ID, RUN_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/${PROJECT_ID}/runs/${RUN_ID}/impact/acknowledge`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      }),
    );
    expect(result.status).toBe("pending_gate_1");
    expect(result.run_id).toBe(RUN_ID);
  });
});
