import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  approveGate,
  getGate1Evidence,
  getGate2Evidence,
  getGateStatus,
  rejectGate,
} from "./gates-api";

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

describe("gates-api", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("maps gate status and evidence responses", async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            run_id: "run-1",
            gate_1: null,
            gate_2: null,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            run_id: "run-1",
            destination_object_name: "Customer",
            mapping_snapshot_version: "v1",
            field_bindings: [
              { source_field: "status_code", destination_field: "status", lookup_name: "status_map" },
            ],
            pii_fields: ["email"],
            coverage_gaps: ["notes"],
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            run_id: "run-1",
            lookup_name: "status_map",
            rows: [{ source_value: "A", destination_value: "ACTIVE", state: "confirmed" }],
            confirmed_count: 1,
            unmapped_count: 0,
          }),
          { status: 200 },
        ),
      );

    await expect(getGateStatus("token", "project-1", "run-1")).resolves.toEqual({
      runId: "run-1",
      gate1: null,
      gate2: null,
    });
    await expect(getGate1Evidence("token", "project-1", "run-1")).resolves.toEqual({
      runId: "run-1",
      destinationObjectName: "Customer",
      mappingSnapshotVersion: "v1",
      fieldBindings: [
        { sourceField: "status_code", destinationField: "status", lookupName: "status_map" },
      ],
      piiFields: ["email"],
      coverageGaps: ["notes"],
    });
    await expect(getGate2Evidence("token", "project-1", "run-1")).resolves.toEqual({
      runId: "run-1",
      lookupName: "status_map",
      rows: [{ sourceValue: "A", destinationValue: "ACTIVE", state: "confirmed" }],
      confirmedCount: 1,
      unmappedCount: 0,
    });
  });

  it("posts gate decisions", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          run_id: "run-1",
          gate_1: null,
          gate_2: null,
        }),
        { status: 200 },
      ),
    );
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          run_id: "run-1",
          gate_1: null,
          gate_2: null,
        }),
        { status: 200 },
      ),
    );

    await approveGate("token", "project-1", "run-1", "gate_1", { notes: "OK" });
    await rejectGate("token", "project-1", "run-1", "gate_2", {
      affectedObjects: ["Customer"],
      requiredChanges: "Fix mapping.",
      notes: "Push back.",
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/projects/project-1/runs/run-1/gates/gate-1/approve",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/projects/project-1/runs/run-1/gates/gate-2/reject",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          affected_objects: ["Customer"],
          required_changes: "Fix mapping.",
          notes: "Push back.",
        }),
      }),
    );
  });
});
