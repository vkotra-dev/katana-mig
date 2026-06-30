import { API_BASE_URL } from "./api-base";

export type TargetDbEngine = "mssql" | "oracle" | "postgresql" | "mysql";

export interface ProjectDomainConfig {
  targetDbEngine: TargetDbEngine | null;
  stagingSchema: string | null;
  dryRun: boolean;
  samplePolicy: Record<string, unknown> | null;
  destinationSchemaDdl: string | null;
  environments: string[] | null;
}

export interface LatestRunSummary {
  currentStage: string | null;
  runStatus: string;
  sourceType: string | null;
  stageEnteredAt: string;
}

export interface ProjectDomainConfigInput {
  targetDbEngine?: TargetDbEngine | null;
  stagingSchema?: string | null;
  dryRun?: boolean;
  samplePolicy?: Record<string, unknown> | null;
  destinationSchemaDdl?: string | null;
  environments?: string[] | null;
}

export interface ProjectRecord {
  projectId: string;
  name: string;
  goal: string | null;
  repos: Record<string, unknown>[] | null;
  workspace: Record<string, unknown> | null;
  environment: string | null;
  executionEnvironments: string[] | null;
  modelPolicy: Record<string, unknown> | null;
  canonicalTerms: string[] | null;
  constraints: string[] | null;
  unresolvedQuestions: string[] | null;
  assumptions: string[] | null;
  domainConfig: ProjectDomainConfig | null;
  lexiconScope: Record<string, unknown> | null;
  status: "active" | "archived";
  createdAt: string;
  updatedAt: string;
  archivedAt: string | null;
  latestRunSummary?: LatestRunSummary | null;
}

export interface ProjectCreateInput {
  name: string;
  goal?: string | null;
  repos?: Record<string, unknown>[] | null;
  workspace?: Record<string, unknown> | null;
  environment?: string | null;
  executionEnvironments?: string[] | null;
  modelPolicy?: Record<string, unknown> | null;
  canonicalTerms?: string[] | null;
  constraints?: string[] | null;
  unresolvedQuestions?: string[] | null;
  assumptions?: string[] | null;
  domainConfig?: ProjectDomainConfigInput | null;
  lexiconScope?: Record<string, unknown> | null;
}

export interface ProjectUpdateInput extends ProjectCreateInput {}

export interface ProjectApiErrorShape {
  code: string;
  message: string;
  status: number;
}

export class ProjectApiError extends Error implements ProjectApiErrorShape {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "ProjectApiError";
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

async function parseApiError(response: Response): Promise<ProjectApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string };
    };
    const code = body.error?.code ?? "api_error";
    const message = body.error?.message ?? code;
    return new ProjectApiError(code, message, response.status);
  } catch {
    const message = await response.text();
    return new ProjectApiError("api_error", message || "api_error", response.status);
  }
}

function mapDomainConfig(config: {
  target_db_engine?: TargetDbEngine | null;
  staging_schema?: string | null;
  dry_run?: boolean;
  sample_policy?: Record<string, unknown> | null;
  destination_schema_ddl?: string | null;
  environments?: string[] | null;
} | null): ProjectDomainConfig | null {
  if (!config) {
    return null;
  }

  return {
    targetDbEngine: config.target_db_engine ?? null,
    stagingSchema: config.staging_schema ?? null,
    dryRun: config.dry_run ?? false,
    samplePolicy: config.sample_policy ?? null,
    destinationSchemaDdl: config.destination_schema_ddl ?? null,
    environments: config.environments ?? null,
  };
}

function serializeDomainConfig(config: ProjectDomainConfigInput | null | undefined):
  | {
      target_db_engine?: TargetDbEngine | null;
      staging_schema?: string | null;
      dry_run?: boolean;
      sample_policy?: Record<string, unknown> | null;
      destination_schema_ddl?: string | null;
      environments?: string[] | null;
    }
  | undefined {
  if (!config) {
    return undefined;
  }

  return {
    target_db_engine: config.targetDbEngine,
    staging_schema: config.stagingSchema,
    dry_run: config.dryRun ?? false,
    sample_policy: config.samplePolicy,
    destination_schema_ddl: config.destinationSchemaDdl,
    environments: config.environments,
  };
}

function mapProjectRecord(record: {
  project_id: string;
  name: string;
  goal: string | null;
  repos: Record<string, unknown>[] | null;
  workspace: Record<string, unknown> | null;
  environment: string | null;
  execution_environments: string[] | null;
  model_policy: Record<string, unknown> | null;
  canonical_terms: string[] | null;
  constraints: string[] | null;
  unresolved_questions: string[] | null;
  assumptions: string[] | null;
  domain_config: {
    target_db_engine?: TargetDbEngine | null;
    staging_schema?: string | null;
    dry_run?: boolean;
    sample_policy?: Record<string, unknown> | null;
    destination_schema_ddl?: string | null;
    environments?: string[] | null;
  } | null;
  lexicon_scope: Record<string, unknown> | null;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  latest_run_summary: {
    current_stage: string | null;
    run_status: string;
    source_type: string | null;
    stage_entered_at: string;
  } | null;
}): ProjectRecord {
  return {
    projectId: record.project_id,
    name: record.name,
    goal: record.goal,
    repos: record.repos,
    workspace: record.workspace,
    environment: record.environment,
    executionEnvironments: record.execution_environments,
    modelPolicy: record.model_policy,
    canonicalTerms: record.canonical_terms,
    constraints: record.constraints,
    unresolvedQuestions: record.unresolved_questions,
    assumptions: record.assumptions,
    domainConfig: mapDomainConfig(record.domain_config),
    lexiconScope: record.lexicon_scope,
    status: record.status,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    archivedAt: record.archived_at,
    latestRunSummary: record.latest_run_summary
      ? {
          currentStage: record.latest_run_summary.current_stage,
          runStatus: record.latest_run_summary.run_status,
          sourceType: record.latest_run_summary.source_type,
          stageEnteredAt: record.latest_run_summary.stage_entered_at,
        }
      : null,
  };
}

function toProjectPayload(input: ProjectCreateInput | ProjectUpdateInput): Record<string, unknown> {
  return {
    name: input.name,
    goal: input.goal,
    repos: input.repos,
    workspace: input.workspace,
    environment: input.environment,
    execution_environments: input.executionEnvironments,
    model_policy: input.modelPolicy,
    canonical_terms: input.canonicalTerms,
    constraints: input.constraints,
    unresolved_questions: input.unresolvedQuestions,
    assumptions: input.assumptions,
    domain_config: serializeDomainConfig(input.domainConfig),
    lexicon_scope: input.lexiconScope,
  };
}

export async function listProjects(
  token: string,
  opts?: { includeArchived?: boolean },
): Promise<ProjectRecord[]> {
  const query = opts?.includeArchived ? "?include_archived=true" : "";
  const response = await requestJson<
    Array<Parameters<typeof mapProjectRecord>[0]>
  >(`/projects${query}`, {
    method: "GET",
    token,
  });

  return response.map(mapProjectRecord);
}

export async function getProject(token: string, id: string): Promise<ProjectRecord> {
  const response = await requestJson<Parameters<typeof mapProjectRecord>[0]>(`/projects/${id}`, {
    method: "GET",
    token,
  });

  return mapProjectRecord(response);
}

export async function createProject(
  token: string,
  body: ProjectCreateInput,
): Promise<ProjectRecord> {
  const response = await requestJson<Parameters<typeof mapProjectRecord>[0]>(`/projects`, {
    method: "POST",
    token,
    body: JSON.stringify(toProjectPayload(body)),
  });

  return mapProjectRecord(response);
}

export async function updateProject(
  token: string,
  id: string,
  body: ProjectUpdateInput,
): Promise<ProjectRecord> {
  const response = await requestJson<Parameters<typeof mapProjectRecord>[0]>(
    `/projects/${id}`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify(toProjectPayload(body)),
    },
  );

  return mapProjectRecord(response);
}

export async function archiveProject(token: string, id: string): Promise<ProjectRecord> {
  const response = await requestJson<Parameters<typeof mapProjectRecord>[0]>(
    `/projects/${id}/archive`,
    {
      method: "POST",
      token,
    },
  );

  return mapProjectRecord(response);
}

export function projectErrorMessage(error: unknown): string {
  if (error instanceof ProjectApiError) {
    if (error.code === "project_not_found") {
      return "Project not found.";
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unable to load project.";
}
