import { afterEach, describe, expect, it, vi } from "vitest";
import {
  archiveProject,
  createProject,
  getProject,
  listProjects,
  type ProjectRecord,
} from "./projects-api";

const BASE = "http://127.0.0.1:8000";

const projectResponse = {
  project_id: "project-1",
  name: "Alpha Migration",
  goal: "Migrate CRM",
  repos: null,
  workspace: null,
  environment: null,
  execution_environments: ["STG", "PROD"],
  model_policy: null,
  canonical_terms: null,
  constraints: ["GDPR"],
  unresolved_questions: null,
  assumptions: null,
  domain_config: {
    target_db_engine: "mssql",
    staging_schema: "stg",
    dry_run: false,
    sample_policy: null,
    destination_schema_ddl: "create table crm(id int);",
    environments: ["dev", "prod"],
  },
  lexicon_scope: null,
  status: "active",
  created_at: "2026-06-30T00:00:00Z",
  updated_at: "2026-06-30T00:00:00Z",
  archived_at: null,
  latest_run_summary: {
    current_stage: "implementation",
    run_status: "running",
    source_type: "csv",
    stage_entered_at: "2026-06-29T00:00:00Z",
  },
};

const project: ProjectRecord = {
  projectId: "project-1",
  name: "Alpha Migration",
  goal: "Migrate CRM",
  repos: null,
  workspace: null,
  environment: null,
  executionEnvironments: ["STG", "PROD"],
  modelPolicy: null,
  canonicalTerms: null,
  constraints: ["GDPR"],
  unresolvedQuestions: null,
  assumptions: null,
  domainConfig: {
    targetDbEngine: "mssql",
    stagingSchema: "stg",
    dryRun: false,
    samplePolicy: null,
    destinationSchemaDdl: "create table crm(id int);",
    environments: ["dev", "prod"],
  },
  lexiconScope: null,
  status: "active",
  createdAt: "2026-06-30T00:00:00Z",
  updatedAt: "2026-06-30T00:00:00Z",
  archivedAt: null,
  latestRunSummary: {
    currentStage: "implementation",
    runStatus: "running",
    sourceType: "csv",
    stageEnteredAt: "2026-06-29T00:00:00Z",
  },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("listProjects", () => {
  it("calls GET /projects with auth headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [projectResponse],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listProjects("token-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result[0].projectId).toBe("project-1");
  });

  it("adds include_archived when requested", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    await listProjects("token-1", { includeArchived: true });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects?include_archived=true`,
      expect.anything(),
    );
  });
});

describe("getProject", () => {
  it("calls GET /projects/{id}", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => projectResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getProject("token-1", "project-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1`,
      expect.anything(),
    );
    expect(result.name).toBe("Alpha Migration");
  });

  it("throws the API error code on 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({
          error: { code: "project_not_found", message: "Project not found." },
        }),
      }),
    );

    await expect(getProject("token-1", "missing")).rejects.toMatchObject({
      code: "project_not_found",
    });
  });
});

describe("createProject", () => {
  it("posts a project create payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => projectResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createProject("token-1", {
      name: "Alpha Migration",
      goal: "Migrate CRM",
      domainConfig: {
        targetDbEngine: "mssql",
        stagingSchema: "stg",
        dryRun: false,
        samplePolicy: { maxRows: 1000 },
        destinationSchemaDdl: "create table crm(id int);",
        environments: ["dev", "prod"],
      },
      executionEnvironments: ["STG", "PROD"],
      constraints: ["GDPR"],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
        body: expect.any(String),
      }),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      name: "Alpha Migration",
      goal: "Migrate CRM",
      execution_environments: ["STG", "PROD"],
      constraints: ["GDPR"],
      domain_config: {
        target_db_engine: "mssql",
        staging_schema: "stg",
        dry_run: false,
        sample_policy: { maxRows: 1000 },
        destination_schema_ddl: "create table crm(id int);",
        environments: ["dev", "prod"],
      },
    });
    expect(result.projectId).toBe("project-1");
  });
});

describe("archiveProject", () => {
  it("posts to /projects/{id}/archive", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...projectResponse,
        status: "archived",
        archived_at: "2026-06-30T01:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await archiveProject("token-1", "project-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/project-1/archive`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result.status).toBe("archived");
  });
});
