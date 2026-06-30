import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveMappingSnapshot,
  getLatestApprovedMappingSnapshot,
  getMappingSnapshot,
  patchMappingSnapshot,
  proposeMappingSnapshot,
  rejectMappingSnapshot,
} from "./mapping-api";

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

  it("loads the mapping review snapshot and parses destination fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        mapping_snapshot_id: "mapping-1",
        project_id: "project-1",
        destination_object_name: "Customer",
        mapping_snapshot_version: "v1",
        field_bindings: [
          {
            source_field: "status_code",
            destination_field: "customer_status",
            lookup_name: null,
          },
        ],
        status: "draft",
        approved_at: null,
        approved_by_user_id: null,
        created_at: "2026-06-30T00:00:00Z",
        destination_fields: ["customer_id", "customer_status"],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getMappingSnapshot("token-1", "project-1", "source-1");

    expect(result.destinationFields).toEqual(["customer_id", "customer_status"]);
    expect(result.fieldBindings[0]?.destinationField).toBe("customer_status");
  });

  it("throws a mapping api error with status details on failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({
        error: {
          code: "mapping_not_found",
          message: "No mapping snapshot exists yet.",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getMappingSnapshot("token-1", "project-1", "source-1")).rejects.toMatchObject({
      name: "MappingApiError",
      code: "mapping_not_found",
      status: 404,
    });
  });

  it("creates, patches, approves, and rejects mapping review snapshots", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          mapping_snapshot_id: "mapping-1",
          project_id: "project-1",
          destination_object_name: "Customer",
          mapping_snapshot_version: "v1",
          field_bindings: [],
          status: "draft",
          approved_at: null,
          approved_by_user_id: null,
          created_at: "2026-06-30T00:00:00Z",
          destination_fields: ["customer_id"],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          mapping_snapshot_id: "mapping-1",
          project_id: "project-1",
          destination_object_name: "Customer",
          mapping_snapshot_version: "v1",
          field_bindings: [
            {
              source_field: "cust_id",
              destination_field: "customer_id",
              lookup_name: null,
            },
          ],
          status: "draft",
          approved_at: null,
          approved_by_user_id: null,
          created_at: "2026-06-30T00:00:00Z",
          destination_fields: ["customer_id"],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          mapping_snapshot_id: "mapping-1",
          project_id: "project-1",
          destination_object_name: "Customer",
          mapping_snapshot_version: "v1",
          field_bindings: [
            {
              source_field: "cust_id",
              destination_field: "customer_id",
              lookup_name: null,
            },
          ],
          status: "approved",
          approved_at: "2026-06-30T01:00:00Z",
          approved_by_user_id: "user-1",
          created_at: "2026-06-30T00:00:00Z",
          destination_fields: ["customer_id"],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          mapping_snapshot_id: "mapping-1",
          project_id: "project-1",
          destination_object_name: "Customer",
          mapping_snapshot_version: "v1",
          field_bindings: [
            {
              source_field: "cust_id",
              destination_field: "customer_id",
              lookup_name: null,
            },
          ],
          status: "rejected",
          approved_at: null,
          approved_by_user_id: null,
          created_at: "2026-06-30T00:00:00Z",
          destination_fields: ["customer_id"],
        }),
      });
    vi.stubGlobal("fetch", fetchMock);

    await expect(proposeMappingSnapshot("token-1", "project-1", "source-1")).resolves.toMatchObject({
      status: "draft",
    });
    await expect(
      patchMappingSnapshot("token-1", "project-1", "source-1", [
        { sourceField: "cust_id", destinationField: "customer_id", lookupName: null },
      ]),
    ).resolves.toMatchObject({
      status: "draft",
    });
    await expect(approveMappingSnapshot("token-1", "project-1", "source-1")).resolves.toMatchObject({
      status: "approved",
    });
    await expect(rejectMappingSnapshot("token-1", "project-1", "source-1", "Needs changes")).resolves.toMatchObject({
      status: "rejected",
    });
  });
});
