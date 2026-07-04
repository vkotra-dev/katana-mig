import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectEditForm } from "../ProjectEditForm";
import type { ProjectRecord } from "../../../lib/projects-api";

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
    destinationSchema: "dbo",
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

const modelDefaults = {
  piiReview: "pii-model",
  fieldMapping: "field-model",
  lookupMapping: "lookup-model",
  scriptGeneration: "script-generation-model",
  scriptCorrection: "script-correction-model",
  schemaDependency: "schema-dependency-model",
  impactAnalysis: "impact-model",
  feedAnalysis: "feed-analysis-model",
  planning: "planning-model",
  review: "review-model",
  implementation: "implementation-model",
};

describe("ProjectEditForm", () => {
  it("prefills and submits the project update payload", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    render(<ProjectEditForm modelDefaults={modelDefaults} project={project} onSubmit={onSubmit} />);

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
    render(
      <ProjectEditForm
        modelDefaults={modelDefaults}
        project={{ ...project, projectResources: null }}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Bold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bullet list" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Center" })).toBeInTheDocument();
  });

  it("renders the rich text toolbar", () => {
    render(<ProjectEditForm modelDefaults={modelDefaults} project={project} onSubmit={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Bold" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bullet list" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Center" })).toBeInTheDocument();
  });

  it("renders the Model Policy section with task inputs", () => {
    render(<ProjectEditForm modelDefaults={modelDefaults} project={project} onSubmit={vi.fn()} />);

    expect(screen.getByRole("button", { name: /Model Policy/i })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Field mapping model" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Model Policy/i }));

    expect(screen.getByRole("textbox", { name: "Field mapping model" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Script generation model" })).toBeInTheDocument();
    expect(screen.getByText("Global default: field-model")).toBeInTheDocument();
    expect(screen.getByText("Global default: planning-model")).toBeInTheDocument();
  });

  it("renders structured sample policy controls", () => {
    render(<ProjectEditForm modelDefaults={modelDefaults} project={project} onSubmit={vi.fn()} />);

    expect(screen.queryByLabelText("Execution environments")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Staging schema" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Destination schema" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Sample policy strategy" })).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "Sample policy max rows" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Sample policy stratified column" })).not.toBeInTheDocument();
  });

  it("shows the stratified column field when stratified sampling is selected", () => {
    render(<ProjectEditForm modelDefaults={modelDefaults} project={project} onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByRole("combobox", { name: "Sample policy strategy" }), {
      target: { value: "stratified" },
    });

    expect(screen.getByRole("textbox", { name: "Sample policy stratified column" })).toBeInTheDocument();
  });

  it("includes modelPolicy and structured sample policy overrides in submit payload", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ProjectEditForm modelDefaults={modelDefaults} project={project} onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /Model Policy/i }));

    fireEvent.change(screen.getByRole("textbox", { name: "Field mapping model" }), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Destination schema" }), {
      target: { value: "archive" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Sample policy strategy" }), {
      target: { value: "stratified" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Sample policy max rows" }), {
      target: { value: "500" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Sample policy stratified column" }), {
      target: { value: "region" },
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
          domainConfig: expect.objectContaining({
            destinationSchema: "archive",
            samplePolicy: {
              strategy: "stratified",
              maxRows: 500,
              stratifiedColumn: "region",
            },
          }),
        }),
      ),
    );
    expect(onSubmit.mock.calls[0]?.[0]?.modelPolicy).not.toHaveProperty("fieldMapping");
  });

  it("clears the model policy when every override is blank", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ProjectEditForm
        modelDefaults={modelDefaults}
        project={{ ...project, modelPolicy: null }}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.submit(
      screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement,
    );

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          modelPolicy: null,
          domainConfig: expect.objectContaining({
            destinationSchema: "dbo",
            samplePolicy: null,
          }),
        }),
      ),
    );
  });

  it("shows an inline error when sample policy max rows is invalid", async () => {
    const onSubmit = vi.fn();

    render(<ProjectEditForm modelDefaults={modelDefaults} project={project} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByRole("spinbutton", { name: "Sample policy max rows" }), {
      target: { value: "0" },
    });
    fireEvent.submit(
      screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Sample policy max rows must be a positive integer.");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("includes projectResources in the submit payload", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ProjectEditForm project={project} onSubmit={onSubmit} />);

    fireEvent.submit(screen.getByRole("button", { name: "Save changes" }).closest("form") as HTMLFormElement);

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          projectResources: expect.any(String),
        })
      )
    );
  });

  it("renders the Project Resources editor last in the form", () => {
    render(<ProjectEditForm project={project} onSubmit={vi.fn()} />);
    const buttons = screen.getAllByRole("button");
    const saveIndex = buttons.findIndex((b) => b.textContent === "Save changes");
    const boldIndex = buttons.findIndex((b) => b.getAttribute("aria-label") === "Bold");
    // Bold toolbar button appears before Save changes
    expect(boldIndex).toBeLessThan(saveIndex);
  });
});
