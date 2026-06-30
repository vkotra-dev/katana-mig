import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveLookupSnapshot,
  createLookupValueMap,
  generateLookupSnapshot,
  listLookupValueMaps,
} from "./lookup-api";

const BASE = "http://127.0.0.1:8000";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("lookup-api", () => {
  it("creates lookup value maps", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        lookup_value_map_id: "map-1",
        source_definition_id: "source-1",
        lookup_name: "status_code",
        destination_table: [{ id: "ACTIVE", label: "Active" }],
        status: "draft",
        created_at: "2026-06-30T00:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createLookupValueMap("token-1", "project-1", "source-1", {
      lookupName: "status_code",
      destinationTable: [{ id: "ACTIVE", label: "Active" }],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/lookup-maps`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
        body: JSON.stringify({
          lookup_name: "status_code",
          destination_table: [{ id: "ACTIVE", label: "Active" }],
        }),
      }),
    );
    expect(result.lookupValueMapId).toBe("map-1");
  });

  it("lists lookup value maps", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          lookup_value_map_id: "map-1",
          source_definition_id: "source-1",
          lookup_name: "status_code",
          destination_table: [],
          status: "approved",
          created_at: "2026-06-30T00:00:00Z",
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listLookupValueMaps("token-1", "project-1", "source-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/lookup-maps`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result[0].status).toBe("approved");
  });

  it("generates lookup snapshots", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        lookup_snapshot_id: "snapshot-1",
        project_id: "project-1",
        source_definition_id: "source-1",
        lookup_name: "status_code",
        lookup_snapshot_version: "v1",
        value_map: { A: "ACTIVE" },
        status: "draft",
        created_at: "2026-06-30T00:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await generateLookupSnapshot("token-1", "project-1", "source-1", {
      lookupName: "status_code",
      valueMap: { A: "ACTIVE" },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/lookup-snapshots`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ lookup_name: "status_code", value_map: { A: "ACTIVE" } }),
      }),
    );
    expect(result.lookupSnapshotVersion).toBe("v1");
  });

  it("approves lookup snapshots", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        lookup_snapshot_id: "snapshot-1",
        project_id: "project-1",
        source_definition_id: "source-1",
        lookup_name: "status_code",
        lookup_snapshot_version: "v1",
        value_map: { A: "ACTIVE" },
        status: "approved",
        created_at: "2026-06-30T00:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await approveLookupSnapshot("token-1", "project-1", "source-1", "snapshot-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/lookup-snapshots/snapshot-1/approve`,
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(result.status).toBe("approved");
  });
});
