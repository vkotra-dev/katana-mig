import { afterEach, describe, expect, it, vi } from "vitest";
import {
  downloadCodegenDeliveryBundle,
  getCodegenArtifact,
  listCodegenArtifacts,
  triggerCodegen,
} from "./codegen-api";

const BASE = "http://127.0.0.1:8000";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("codegen-api", () => {
  it("triggers codegen and maps the returned artifact preview", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        codegen_artifact_id: "cga-1",
        project_id: "project-1",
        destination_object_name: "Customer",
        status: "active",
        sql_bundle_preview: "CREATE TABLE stg_customer (",
        source_slice_version: "v1",
        mapping_snapshot_version: "v1",
        lookup_snapshot_version: null,
        created_at: "2026-06-30T00:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await triggerCodegen("token-1", "project-1", "source-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/sources/source-1/codegen`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result.codegenArtifactId).toBe("cga-1");
    expect(result.sqlBundlePreview).toContain("CREATE TABLE");
  });

  it("lists codegen artifacts and fetches full artifacts", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            codegen_artifact_id: "cga-1",
            project_id: "project-1",
            destination_object_name: "Customer",
            run_id: null,
            source_slice_version: "v1",
            mapping_snapshot_version: "v1",
            lookup_snapshot_version: null,
            sql_bundle: "CREATE TABLE stg_customer ();",
            status: "active",
            created_at: "2026-06-30T00:00:00Z",
            superseded_at: null,
          },
        ],
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          codegen_artifact_id: "cga-1",
          project_id: "project-1",
          destination_object_name: "Customer",
          run_id: null,
          source_slice_version: "v1",
          mapping_snapshot_version: "v1",
          lookup_snapshot_version: null,
          sql_bundle: "CREATE TABLE stg_customer ();",
          status: "active",
          created_at: "2026-06-30T00:00:00Z",
          superseded_at: null,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        text: async () => "-- Customer\n\nCREATE TABLE stg_customer ();",
      });
    vi.stubGlobal("fetch", fetchMock);

    const list = await listCodegenArtifacts("token-1", "project-1");
    const artifact = await getCodegenArtifact("token-1", "project-1", "cga-1");
    const bundle = await downloadCodegenDeliveryBundle("token-1", "project-1");

    expect(list[0]?.destinationObjectName).toBe("Customer");
    expect(artifact.sqlBundle).toContain("CREATE TABLE");
    expect(bundle).toContain("-- Customer");
  });
});
