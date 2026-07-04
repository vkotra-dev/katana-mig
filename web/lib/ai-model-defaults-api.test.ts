import { afterEach, describe, expect, it, vi } from "vitest";
import { getAiModelDefaults } from "./ai-model-defaults-api";

const BASE = "http://127.0.0.1:8000";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ai-model-defaults-api", () => {
  it("fetches the resolved defaults with auth headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        source: "engine.yaml",
        platform_models: {
          planning: "planning-model",
          review: "review-model",
          implementation: "implementation-model",
        },
        migration_models: {
          pii_review: "pii-model",
          field_mapping: "field-model",
          lookup_mapping: "lookup-model",
          script_generation: "script-generation-model",
          script_correction: "script-correction-model",
          schema_dependency: "schema-dependency-model",
          impact_analysis: "impact-model",
          feed_analysis: "feed-analysis-model",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getAiModelDefaults("token-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/config/ai-model-defaults`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result).toEqual({
      source: "engine.yaml",
      platformModels: {
        planning: "planning-model",
        review: "review-model",
        implementation: "implementation-model",
      },
      migrationModels: {
        piiReview: "pii-model",
        fieldMapping: "field-model",
        lookupMapping: "lookup-model",
        scriptGeneration: "script-generation-model",
        scriptCorrection: "script-correction-model",
        schemaDependency: "schema-dependency-model",
        impactAnalysis: "impact-model",
        feedAnalysis: "feed-analysis-model",
      },
    });
  });
});
