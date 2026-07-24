import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveLookupSnapshot,
  createLookupValueMap,
  generateLookupSnapshot,
  listLookupValueMaps,
  patchLookupValueMap,
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
        project_id: "project-1",
        lookup_name: "status_code",
        destination_table: [{ id: "ACTIVE", label: "Active" }],
        source_value_map: { A: "ACTIVE" },
        status: "draft",
        created_at: "2026-06-30T00:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createLookupValueMap("token-1", "project-1", {
      lookupName: "status_code",
      destinationTable: [{ id: "ACTIVE", label: "Active" }],
      sourceValueMap: { A: "ACTIVE" },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/lookup-maps`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
        body: JSON.stringify({
          lookup_name: "status_code",
          destination_table: [{ id: "ACTIVE", label: "Active" }],
          source_value_map: { A: "ACTIVE" },
        }),
      }),
    );
    expect(result.lookupValueMapId).toBe("map-1");
    expect(result.projectId).toBe("project-1");
  });

  it("lists lookup value maps", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          lookup_value_map_id: "map-1",
          project_id: "project-1",
          lookup_name: "status_code",
          destination_table: [],
          source_value_map: {},
          status: "approved",
          created_at: "2026-06-30T00:00:00Z",
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listLookupValueMaps("token-1", "project-1", "source-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/lookup-maps?feed_id=source-1`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result[0].status).toBe("approved");
    expect(result[0].projectId).toBe("project-1");
  });

  it("generates lookup snapshots", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        lookup_snapshot_id: "snapshot-1",
        project_id: "project-1",
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
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/lookup-snapshots`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ lookup_name: "status_code" }),
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
        lookup_name: "status_code",
        lookup_snapshot_version: "v1",
        value_map: { A: "ACTIVE" },
        status: "approved",
        created_at: "2026-06-30T00:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await approveLookupSnapshot("token-1", "project-1", "snapshot-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/lookup-snapshots/snapshot-1/approve`,
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(result.status).toBe("approved");
  });

  describe("patchLookupValueMap", () => {
    it("sends addSourceValue as add_source_value in the request body", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          lookup_value_map_id: "map-1",
          project_id: "project-1",
          lookup_name: "status_code",
          destination_table: [{ id: "ACTIVE", label: "Active" }],
          source_value_map: { A: "ACTIVE" },
          destination_mappings: [
            { dest_id: "ACTIVE", dest_label: "Active", source_values: ["A"], status: "draft" },
          ],
          status: "draft",
          created_at: "2026-06-30T00:00:00Z",
        }),
      });
      vi.stubGlobal("fetch", fetchMock);

      await patchLookupValueMap("token-1", "project-1", "map-1", {
        addSourceValue: { destId: "ACTIVE", sourceValue: "active_status" },
      });

      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE}/projects/project-1/lookup-maps/map-1`,
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            add_source_value: { destId: "ACTIVE", sourceValue: "active_status" },
          }),
        }),
      );
    });

    it("sends removeSourceValue as remove_source_value (snake_case) in the request body", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          lookup_value_map_id: "map-1",
          project_id: "project-1",
          lookup_name: "status_code",
          destination_table: [{ id: "ACTIVE", label: "Active" }],
          source_value_map: {},
          destination_mappings: [],
          status: "draft",
          created_at: "2026-06-30T00:00:00Z",
        }),
      });
      vi.stubGlobal("fetch", fetchMock);

      await patchLookupValueMap("token-1", "project-1", "map-1", {
        removeSourceValue: { destId: "ACTIVE", sourceValue: "old_alias" },
      });

      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE}/projects/project-1/lookup-maps/map-1`,
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            remove_source_value: { destId: "ACTIVE", sourceValue: "old_alias" },
          }),
        }),
      );
    });

    it("sends moveSourceValue as move_source_value in the request body", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          lookup_value_map_id: "map-1",
          project_id: "project-1",
          lookup_name: "status_code",
          destination_table: [{ id: "ACTIVE", label: "Active" }],
          source_value_map: { A: "ACTIVE" },
          destination_mappings: [
            { dest_id: "ACTIVE", dest_label: "Active", source_values: ["A"], status: "draft" },
          ],
          status: "draft",
          created_at: "2026-06-30T00:00:00Z",
        }),
      });
      vi.stubGlobal("fetch", fetchMock);

      await patchLookupValueMap("token-1", "project-1", "map-1", {
        moveSourceValue: { sourceValue: "A", oldDestId: "OLD", newDestId: "ACTIVE" },
      });

      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE}/projects/project-1/lookup-maps/map-1`,
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            move_source_value: { sourceValue: "A", oldDestId: "OLD", newDestId: "ACTIVE" },
          }),
        }),
      );
    });
  });
});
