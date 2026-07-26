import { API_BASE_URL } from "./api-base";

export type TargetDbEngine = "mssql" | "oracle" | "postgresql" | "mysql";

export type SamplePolicyStrategy = "random" | "top_n" | "full" | "stratified";

export interface SamplePolicy {
  strategy: SamplePolicyStrategy;
  maxRows: number | null;
  stratifiedColumn: string | null;
}

export interface ProjectDomainConfig {
  targetDbEngine: TargetDbEngine | null;
  stagingSchema: string | null;
  destinationSchema: string | null;
  dryRun: boolean;
  samplePolicy: SamplePolicy | null;
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
  destinationSchema?: string | null;
  dryRun?: boolean;
  samplePolicy?: SamplePolicy | null;
  destinationSchemaDdl?: string | null;
  environments?: string[] | null;
}

export interface ModelPolicy {
  piiReview?: string | null;
  fieldMapping?: string | null;
  lookupMapping?: string | null;
  scriptGeneration?: string | null;
  scriptCorrection?: string | null;
  schemaDependency?: string | null;
  impactAnalysis?: string | null;
  feedAnalysis?: string | null;
  planning?: string | null;
  review?: string | null;
  implementation?: string | null;
}

type RawModelPolicy = {
  pii_review?: string | null;
  field_mapping?: string | null;
  lookup_mapping?: string | null;
  script_generation?: string | null;
  script_correction?: string | null;
  schema_dependency?: string | null;
  impact_analysis?: string | null;
  feed_analysis?: string | null;
  planning?: string | null;
  review?: string | null;
  implementation?: string | null;
};

export type HealthStatus = "healthy" | "pending_review" | "needs_attention";

export interface ProjectHealthSummary {
  feedStatus: HealthStatus;
  mappingStatus: HealthStatus;
  lookupStatus: HealthStatus;
}

export interface ProjectRecord {
  projectId: string;
  name: string;
  goal: string | null;
  repos: Record<string, unknown>[] | null;
  workspace: Record<string, unknown> | null;
  projectResources?: string | null;
  executionEnvironments: string[] | null;
  modelPolicy: ModelPolicy | null;
  canonicalTerms: string[] | null;
  constraints: string[] | null;
  unresolvedQuestions: string[] | null;
  assumptions: string[] | null;
  domainConfig: ProjectDomainConfig | null;
  lexiconScope: string | null;
  status: "active" | "archived";
  createdAt: string;
  updatedAt: string;
  archivedAt: string | null;
  latestRunSummary?: LatestRunSummary | null;
  health?: ProjectHealthSummary;
  pmUserId?: string | null;
  codegenInstructions?: string | null;
}

export interface ProjectCreateInput {
  name: string;
  goal?: string | null;
  repos?: Record<string, unknown>[] | null;
  workspace?: Record<string, unknown> | null;
  projectResources?: string | null;
  executionEnvironments?: string[] | null;
  modelPolicy?: ModelPolicy | null;
  canonicalTerms?: string[] | null;
  constraints?: string[] | null;
  unresolvedQuestions?: string[] | null;
  assumptions?: string[] | null;
  domainConfig?: ProjectDomainConfigInput | null;
  lexiconScope?: string | null;
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
  destination_schema?: string | null;
  dry_run?: boolean;
  sample_policy?: {
    strategy?: SamplePolicyStrategy | null;
    max_rows?: number | null;
    stratified_column?: string | null;
  } | null;
  destination_schema_ddl?: string | null;
  environments?: string[] | null;
} | null): ProjectDomainConfig | null {
  if (!config) {
    return null;
  }

  return {
    targetDbEngine: config.target_db_engine ?? null,
    stagingSchema: config.staging_schema ?? null,
    destinationSchema: config.destination_schema ?? null,
    dryRun: config.dry_run ?? false,
    samplePolicy: config.sample_policy
      ? {
          strategy: config.sample_policy.strategy ?? "random",
          maxRows: config.sample_policy.max_rows ?? null,
          stratifiedColumn: config.sample_policy.stratified_column ?? null,
        }
      : null,
    destinationSchemaDdl: config.destination_schema_ddl ?? null,
    environments: config.environments ?? null,
  };
}

function mapModelPolicy(policy: RawModelPolicy | null): ModelPolicy | null {
  if (!policy) {
    return null;
  }

  return {
    piiReview: policy.pii_review ?? null,
    fieldMapping: policy.field_mapping ?? null,
    lookupMapping: policy.lookup_mapping ?? null,
    scriptGeneration: policy.script_generation ?? null,
    scriptCorrection: policy.script_correction ?? null,
    schemaDependency: policy.schema_dependency ?? null,
    impactAnalysis: policy.impact_analysis ?? null,
    feedAnalysis: policy.feed_analysis ?? null,
    planning: policy.planning ?? null,
    review: policy.review ?? null,
    implementation: policy.implementation ?? null,
  };
}

function serializeModelPolicy(policy: ModelPolicy | null | undefined):
  | {
      pii_review?: string | null;
      field_mapping?: string | null;
      lookup_mapping?: string | null;
      script_generation?: string | null;
      script_correction?: string | null;
      schema_dependency?: string | null;
      impact_analysis?: string | null;
      feed_analysis?: string | null;
      planning?: string | null;
    review?: string | null;
    implementation?: string | null;
  }
  | null
  | undefined {
  if (policy === null) {
    return null;
  }
  if (!policy) {
    return undefined;
  }

  const serialized: {
    pii_review?: string;
    field_mapping?: string;
    lookup_mapping?: string;
    script_generation?: string;
    script_correction?: string;
    schema_dependency?: string;
    impact_analysis?: string;
    feed_analysis?: string;
    planning?: string;
    review?: string;
    implementation?: string;
  } = {};

  if (policy.piiReview) serialized.pii_review = policy.piiReview;
  if (policy.fieldMapping) serialized.field_mapping = policy.fieldMapping;
  if (policy.lookupMapping) serialized.lookup_mapping = policy.lookupMapping;
  if (policy.scriptGeneration) serialized.script_generation = policy.scriptGeneration;
  if (policy.scriptCorrection) serialized.script_correction = policy.scriptCorrection;
  if (policy.schemaDependency) serialized.schema_dependency = policy.schemaDependency;
  if (policy.impactAnalysis) serialized.impact_analysis = policy.impactAnalysis;
  if (policy.feedAnalysis) serialized.feed_analysis = policy.feedAnalysis;
  if (policy.planning) serialized.planning = policy.planning;
  if (policy.review) serialized.review = policy.review;
  if (policy.implementation) serialized.implementation = policy.implementation;

  return Object.keys(serialized).length > 0 ? serialized : null;
}

function serializeDomainConfig(config: ProjectDomainConfigInput | null | undefined):
  | {
      target_db_engine?: TargetDbEngine | null;
      staging_schema?: string | null;
      destination_schema?: string | null;
      dry_run?: boolean;
      sample_policy?: {
        strategy: SamplePolicyStrategy;
        max_rows: number | null;
        stratified_column: string | null;
      } | null;
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
    destination_schema: config.destinationSchema,
    dry_run: config.dryRun ?? false,
    sample_policy: config.samplePolicy
      ? {
          strategy: config.samplePolicy.strategy,
          max_rows: config.samplePolicy.maxRows,
          stratified_column: config.samplePolicy.stratifiedColumn,
        }
      : null,
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
  project_resources: string | null;
  execution_environments: string[] | null;
  model_policy: Record<string, unknown> | null;
  canonical_terms: string[] | null;
  constraints: string[] | null;
  unresolved_questions: string[] | null;
  assumptions: string[] | null;
  domain_config: {
    target_db_engine?: TargetDbEngine | null;
    staging_schema?: string | null;
    destination_schema?: string | null;
    dry_run?: boolean;
    sample_policy?: {
      strategy?: SamplePolicyStrategy | null;
      max_rows?: number | null;
      stratified_column?: string | null;
    } | null;
    destination_schema_ddl?: string | null;
    environments?: string[] | null;
  } | null;
  lexicon_scope: string | null;
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
  health: {
    feed_status: string;
    mapping_status: string;
    lookup_status: string;
  } | null;
  pm_user_id: string | null;
  codegen_instructions?: string | null;
}): ProjectRecord {
  return {
    projectId: record.project_id,
    name: record.name,
    goal: record.goal,
    repos: record.repos,
    workspace: record.workspace,
    projectResources: record.project_resources ?? null,
    executionEnvironments: record.execution_environments,
    modelPolicy: mapModelPolicy(record.model_policy as RawModelPolicy | null),
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
    health: record.health
      ? {
          feedStatus: record.health.feed_status as HealthStatus,
          mappingStatus: record.health.mapping_status as HealthStatus,
          lookupStatus: record.health.lookup_status as HealthStatus,
        }
      : undefined,
    pmUserId: record.pm_user_id ?? null,
    codegenInstructions: record.codegen_instructions ?? null,
  };
}

function toProjectPayload(input: ProjectCreateInput | ProjectUpdateInput): Record<string, unknown> {
  return {
    name: input.name,
    goal: input.goal,
    repos: input.repos,
    workspace: input.workspace,
    project_resources: input.projectResources,
    execution_environments: input.executionEnvironments,
    model_policy: serializeModelPolicy(input.modelPolicy),
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

export async function getCodegenCodingStandardsTemplate(token: string, id: string): Promise<string> {
  const response = await requestJson<{ template: string }>(
    `/projects/${id}/codegen-coding-standards-template`,
    { method: "GET", token },
  );

  return response.template;
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

export interface ProjectCopyInput {
  name: string;
  stakeholderUserIds: string[];
}

export async function copyProject(
  token: string,
  sourceProjectId: string,
  input: ProjectCopyInput,
): Promise<ProjectRecord> {
  const response = await requestJson<Parameters<typeof mapProjectRecord>[0]>(
    `/projects/${sourceProjectId}/copy`,
    {
      method: "POST",
      token,
      body: JSON.stringify({
        name: input.name,
        stakeholder_user_ids: input.stakeholderUserIds,
      }),
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

export async function assignProjectManager(
  token: string,
  projectId: string,
  pmUserId: string,
): Promise<ProjectRecord> {
  const data = await requestJson<Parameters<typeof mapProjectRecord>[0]>(
    `/projects/${projectId}/manager`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({ pm_user_id: pmUserId }),
    },
  );
  return mapProjectRecord(data);
}

export async function saveCodegenInstructions(
  token: string,
  projectId: string,
  instructions: string | null,
): Promise<ProjectRecord> {
  const data = await requestJson<Parameters<typeof mapProjectRecord>[0]>(
    `/projects/${projectId}/codegen-instructions`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({ codegen_instructions: instructions }),
    },
  );
  return mapProjectRecord(data);
}

export async function resetCodegenInstructions(
  token: string,
  projectId: string,
): Promise<ProjectRecord> {
  const data = await requestJson<Parameters<typeof mapProjectRecord>[0]>(
    `/projects/${projectId}/codegen-instructions/reset`,
    {
      method: "POST",
      token,
    },
  );
  return mapProjectRecord(data);
}
