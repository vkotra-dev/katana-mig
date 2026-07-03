import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getChangeRequest,
  listChangeRequests,
  resolveChangeRequest,
  type ChangeRequestRecord,
  type ChangeRequestSummaryRecord,
} from "./change-requests-api";

const BASE = "http://127.0.0.1:8000";

const summaryResponse = {
  change_request_id: "cr-1",
  project_id: "project-1",
  change_request_type: "lookup_delta",
  status: "open",
  title: "Lookup delta for account_type",
  created_at: "2026-07-01T10:00:00Z",
};

const detailResponse = {
  change_request_id: "cr-1",
  project_id: "project-1",
  change_request_type: "lookup_delta",
  status: "open",
  title: "Lookup delta for account_type",
  payload: {
    run_id: "run-1",
    lookup_name: "account_type",
    unmapped_value: "RETD",
    destination_object_name: "customers",
  },
  created_at: "2026-07-01T10:00:00Z",
  updated_at: "2026-07-01T10:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("listChangeRequests", () => {
  it("calls GET /projects/{id}/change-requests with auth headers and maps to camelCase", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [summaryResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listChangeRequests("token-1", "project-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/change-requests`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
      }),
    );

    const expected: ChangeRequestSummaryRecord = {
      changeRequestId: "cr-1",
      projectId: "project-1",
      changeRequestType: "lookup_delta",
      status: "open",
      title: "Lookup delta for account_type",
      createdAt: "2026-07-01T10:00:00Z",
    };
    expect(result).toEqual([expected]);
  });
});

describe("getChangeRequest", () => {
  it("calls GET /projects/{id}/change-requests/{crId} and maps payload to camelCase", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => detailResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getChangeRequest("token-1", "project-1", "cr-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/change-requests/cr-1`,
      expect.objectContaining({ method: "GET" }),
    );

    const expected: ChangeRequestRecord = {
      changeRequestId: "cr-1",
      projectId: "project-1",
      changeRequestType: "lookup_delta",
      status: "open",
      title: "Lookup delta for account_type",
      payload: {
        runId: "run-1",
        lookupName: "account_type",
        unmappedValue: "RETD",
        destinationObjectName: "customers",
      },
      createdAt: "2026-07-01T10:00:00Z",
      updatedAt: "2026-07-01T10:00:00Z",
    };
    expect(result).toEqual(expected);
  });

  it("handles null payload gracefully", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ...detailResponse, payload: null }),
      }),
    );

    const result = await getChangeRequest("token-1", "project-1", "cr-1");
    expect(result.payload).toBeNull();
  });

  it("throws on 404 with error text", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        text: async () => JSON.stringify({ error: { code: "change_request_not_found", message: "Not found." } }),
      }),
    );

    await expect(getChangeRequest("token-1", "project-1", "missing")).rejects.toThrow();
  });
});

describe("resolveChangeRequest", () => {
  it("posts accepted_value to /resolve and returns resolved status", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ change_request_id: "cr-1", status: "resolved" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await resolveChangeRequest("token-1", "project-1", "cr-1", {
      acceptedValue: "RETIRED",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/change-requests/cr-1/resolve`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer token-1" }),
        body: JSON.stringify({ accepted_value: "RETIRED" }),
      }),
    );
    expect(result.changeRequestId).toBe("cr-1");
    expect(result.status).toBe("resolved");
  });

  it("throws on 409 cr_not_open", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        text: async () => JSON.stringify({ error: { code: "cr_not_open", message: "Already closed." } }),
      }),
    );

    await expect(
      resolveChangeRequest("token-1", "project-1", "cr-1", { acceptedValue: "X" }),
    ).rejects.toThrow();
  });
});
