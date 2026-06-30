import { afterEach, describe, expect, it, vi } from "vitest";
import { getLatestApprovedMappingSnapshot } from "./mapping-api";

const BASE = "http://127.0.0.1:8000";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("mapping-api", () => {
  it("loads the latest approved mapping snapshot for a source", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        mapping_snapshot_id: "mapping-1",
        project_id: "project-1",
        destination_object_name: "Customer",
        mapping_snapshot_version: "v4",
        field_bindings: [
          {
            source_field: "status_code",
            destination_field: "status_id",
            lookup_name: "status_code",
          },
        ],
        status: "approved",
        approved_at: "2026-06-30T00:00:00Z",
        approved_by_user_id: "user-1",
        created_at: "2026-06-30T00:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getLatestApprovedMappingSnapshot("token-1", "project-1", "source-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/mapping-snapshot`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result.mappingSnapshotVersion).toBe("v4");
    expect(result.fieldBindings[0]?.lookupName).toBe("status_code");
  });
});
