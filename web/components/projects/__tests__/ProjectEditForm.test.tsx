import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectEditForm } from "../ProjectEditForm";
import type { ProjectRecord } from "../../../lib/projects-api";
import { PROJECT_RESOURCES_TEMPLATE } from "../projectResourcesTemplate";

const project: ProjectRecord = {
  projectId: "project-abc",
  name: "CRM Migration",
  goal: "Migrate all CRM data",
  repos: null,
  workspace: null,
  projectResources: "== PROD ==\nHost/IP: 10.0.0.1",
  executionEnvironments: ["STG", "UAT", "PROD"],
  modelPolicy: {
    fieldMapping: "claude-opus-4-8",
    planning: "gpt-5",
  },
  canonicalTerms: null,
  constraints: ["GDPR", "Art 6(1)(c)"],
  unresolvedQuestions: ["PHI present?"],
  assumptions: ["Source replica is stable"],
  domainConfig: {
    targetDbEngine: "mssql",
    stagingSchema: "stg",
    dryRun: false,
    samplePolicy: null,
    destinationSchemaDdl: "create table crm(id int);",
    environments: ["dev", "uat", "prod"],
  },
  lexiconScope: null,
  status: "active",
  createdAt: "2026-06-30T00:00:00Z",
  updatedAt: "2026-06-30T01:00:00Z",
  archivedAt: null,
  latestRunSummary: null,
};

describe("ProjectEditForm", () => {
  it("prefills and submits the project update payload", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    render(<ProjectEditForm project={project} onSubmit={onSubmit} />);

    expect(screen.getByDisplayValue("CRM Migration")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Project name"), {
      target: { value: "CRM Migration v2" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement,
    );

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "CRM Migration v2",
          goal: "Migrate all CRM data",
          projectResources: "== PROD ==\nHost/IP: 10.0.0.1",
          executionEnvironments: ["STG", "UAT", "PROD"],
          domainConfig: expect.any(Object),
          modelPolicy: expect.objectContaining({
            fieldMapping: "claude-opus-4-8",
            planning: "gpt-5",
          }),
        }),
      ),
    );
  });

  it("renders the project resources editor when empty", () => {
    render(<ProjectEditForm project={{ ...project, projectResources: null }} onSubmit={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Bold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bullet list" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Center" })).toBeInTheDocument();
  });

  it("renders the rich text toolbar", () => {
    render(<ProjectEditForm project={project} onSubmit={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Bold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bullet list" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Center" })).toBeInTheDocument();
  });

  it("renders the Model Policy section with task inputs", () => {
    render(<ProjectEditForm project={project} onSubmit={vi.fn()} />);

    expect(screen.getByText("Model Policy")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Field mapping model" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Script generation model" })).toBeInTheDocument();
    expect(screen.getAllByPlaceholderText("Global default")).toHaveLength(11);
  });

  it("includes modelPolicy overrides in submit payload", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ProjectEditForm project={project} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByRole("textbox", { name: "Field mapping model" }), {
      target: { value: "" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement,
    );

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          modelPolicy: expect.objectContaining({
            planning: "gpt-5",
          }),
        }),
      ),
    );
    expect(onSubmit.mock.calls[0]?.[0]?.modelPolicy).not.toHaveProperty("fieldMapping");
  });

  it("clears the model policy when every override is blank", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ProjectEditForm project={{ ...project, modelPolicy: null }} onSubmit={onSubmit} />);

    fireEvent.submit(
      screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement,
    );

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          modelPolicy: null,
        }),
      ),
    );
  });

  it("shows an inline error when sample policy JSON is invalid", async () => {
    const onSubmit = vi.fn();

    render(<ProjectEditForm project={project} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Sample policy"), {
      target: { value: "{ not valid json" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Sample policy must be valid JSON.");
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
