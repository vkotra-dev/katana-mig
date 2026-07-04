import { API_BASE_URL } from "./api-base";

export interface PlatformModelDefaultsRecord {
  planning: string;
  review: string;
  implementation: string;
}

export interface MigrationModelDefaultsRecord {
  piiReview: string;
  fieldMapping: string;
  lookupMapping: string;
  scriptGeneration: string;
  scriptCorrection: string;
  schemaDependency: string;
  impactAnalysis: string;
  feedAnalysis: string;
}

export interface AIModelDefaultsRecord {
  source: "engine.yaml";
  platformModels: PlatformModelDefaultsRecord;
  migrationModels: MigrationModelDefaultsRecord;
}

type RawAIModelDefaultsResponse = {
  source: "engine.yaml";
  platform_models: {
    planning: string;
    review: string;
    implementation: string;
  };
  migration_models: {
    pii_review: string;
    field_mapping: string;
    lookup_mapping: string;
    script_generation: string;
    script_correction: string;
    schema_dependency: string;
    impact_analysis: string;
    feed_analysis: string;
  };
};

export class AIModelDefaultsApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "AIModelDefaultsApiError";
    this.code = code;
    this.status = status;
  }
}

function authHeaders(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

async function parseApiError(response: Response): Promise<AIModelDefaultsApiError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    const code = body.error?.code ?? "api_error";
    const message = body.error?.message ?? code;
    return new AIModelDefaultsApiError(code, message, response.status);
  } catch {
    const message = await response.text();
    return new AIModelDefaultsApiError("api_error", message || "api_error", response.status);
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit & { token: string },
): Promise<T> {
  const { token, headers, ...rest } = init;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      ...authHeaders(token),
      ...(headers ?? {}),
    },
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  return (await response.json()) as T;
}

export async function getAiModelDefaults(token: string): Promise<AIModelDefaultsRecord> {
  const response = await requestJson<RawAIModelDefaultsResponse>("/config/ai-model-defaults", {
    method: "GET",
    token,
  });

  return {
    source: response.source,
    platformModels: {
      planning: response.platform_models.planning,
      review: response.platform_models.review,
      implementation: response.platform_models.implementation,
    },
    migrationModels: {
      piiReview: response.migration_models.pii_review,
      fieldMapping: response.migration_models.field_mapping,
      lookupMapping: response.migration_models.lookup_mapping,
      scriptGeneration: response.migration_models.script_generation,
      scriptCorrection: response.migration_models.script_correction,
      schemaDependency: response.migration_models.schema_dependency,
      impactAnalysis: response.migration_models.impact_analysis,
      feedAnalysis: response.migration_models.feed_analysis,
    },
  };
}
