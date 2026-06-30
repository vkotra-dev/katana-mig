import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CreateProjectDialog } from "../CreateProjectDialog";
import type { ProjectRecord } from "../../../lib/projects-api";

const stubResponse = {
  project_id: "project-3",
  name: "New Project",
  goal: "Migrate orders",
  repos: null,
  workspace: null,
  environment: null,
  execution_environments: null,
  model_policy: null,
  canonical_terms: null,
  constraints: null,
  unresolved_questions: null,
  assumptions: null,
  domain_config: {
    target_db_engine: "mssql",
    staging_schema: null,
    dry_run: false,
    sample_policy: null,
    destination_schema_ddl: null,
    environments: null,
  },
  lexicon_scope: null,
  status: "active",
  created_at: "2026-06-30T00:00:00Z",
  updated_at: "2026-06-30T00:00:00Z",
  archived_at: null,
};

const stub: ProjectRecord = {
  projectId: "project-3",
  name: "New Project",
  goal: "Migrate orders",
  repos: null,
  workspace: null,
  environment: null,
  executionEnvironments: null,
  modelPolicy: null,
  canonicalTerms: null,
  constraints: null,
  unresolvedQuestions: null,
  assumptions: null,
  domainConfig: {
    targetDbEngine: "mssql",
    stagingSchema: null,
    dryRun: false,
    samplePolicy: null,
    destinationSchemaDdl: null,
    environments: null,
  },
  lexiconScope: null,
  status: "active",
  createdAt: "2026-06-30T00:00:00Z",
  updatedAt: "2026-06-30T00:00:00Z",
  archivedAt: null,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("CreateProjectDialog", () => {
  it("does not render when closed", () => {
    render(
      <CreateProjectDialog open={false} token="token-1" onCreated={vi.fn()} onClose={vi.fn()} />,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the required project fields", () => {
    render(<CreateProjectDialog open token="token-1" onCreated={vi.fn()} onClose={vi.fn()} />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText(/project name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/goal/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/target database engine/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/source type/i)).not.toBeInTheDocument();
  });

  it("keeps submit disabled until required fields are filled", () => {
    render(<CreateProjectDialog open token="token-1" onCreated={vi.fn()} onClose={vi.fn()} />);

    expect(screen.getByRole("button", { name: /create project/i })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/project name/i), {
      target: { value: "New Project" },
    });

    expect(screen.getByRole("button", { name: /create project/i })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/target database engine/i), {
      target: { value: "mssql" },
    });

    expect(screen.getByRole("button", { name: /create project/i })).not.toBeDisabled();
  });

  it("submits a create payload without source fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => stubResponse,
    });
    vi.stubGlobal("fetch", fetchMock);

    const onCreated = vi.fn();
    const onClose = vi.fn();
    render(<CreateProjectDialog open token="token-1" onCreated={onCreated} onClose={onClose} />);

    fireEvent.change(screen.getByLabelText(/project name/i), {
      target: { value: "New Project" },
    });
    fireEvent.change(screen.getByLabelText(/goal/i), {
      target: { value: "Migrate orders" },
    });
    fireEvent.change(screen.getByLabelText(/target database engine/i), {
      target: { value: "mssql" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create project/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(stub));
    expect(onClose).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/projects",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "New Project",
          goal: "Migrate orders",
          domain_config: {
            target_db_engine: "mssql",
            dry_run: false,
          },
        }),
      }),
    );
  });

  it("renders API failures inline", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({
          error: { code: "forbidden", message: "Forbidden" },
        }),
      }),
    );

    render(<CreateProjectDialog open token="token-1" onCreated={vi.fn()} onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText(/project name/i), {
      target: { value: "New Project" },
    });
    fireEvent.change(screen.getByLabelText(/target database engine/i), {
      target: { value: "mssql" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create project/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
