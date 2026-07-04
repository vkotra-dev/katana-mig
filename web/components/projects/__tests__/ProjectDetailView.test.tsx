import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProjectDetailView } from "../ProjectDetailView";
import type { ProjectRecord } from "../../../lib/projects-api";

const active: ProjectRecord = {
  projectId: "project-abc",
  name: "CRM Migration",
  goal: "Migrate all CRM data",
  repos: null,
  workspace: null,
  projectResources: "== PROD ==\nHost/IP: 10.0.0.1",
  executionEnvironments: ["STG", "UAT", "PROD"],
  modelPolicy: null,
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
  latestRunSummary: {
    currentStage: "implementation",
    runStatus: "running",
    sourceType: "csv",
    stageEnteredAt: "2026-06-29T00:00:00Z",
  },
};

const archived: ProjectRecord = {
  ...active,
  status: "archived",
  archivedAt: "2026-06-30T12:00:00Z",
};

const modelDefaults = {
  piiReview: "pii-model",
  fieldMapping: "field-default",
  lookupMapping: "lookup-default",
  scriptGeneration: "script-default",
  scriptCorrection: "script-correction-default",
  schemaDependency: "schema-dependency-default",
  impactAnalysis: "impact-default",
  feedAnalysis: "feed-analysis-default",
  planning: "planning-model",
  review: "review-model",
  implementation: "implementation-model",
};

describe("ProjectDetailView", () => {
  it("renders project identity and status", () => {
    render(<ProjectDetailView project={active} />);

    expect(screen.getByRole("heading", { name: /crm migration/i })).toBeInTheDocument();
    expect(screen.getByText("project-abc")).toBeInTheDocument();
    expect(screen.getByText(/active/i)).toBeInTheDocument();
  });

  it("renders the project overview fields", () => {
    render(<ProjectDetailView project={active} />);

    expect(screen.getByText("Migrate all CRM data")).toBeInTheDocument();
    expect(screen.getByText("STG → UAT → PROD")).toBeInTheDocument();
    expect(screen.getByText("GDPR, Art 6(1)(c)")).toBeInTheDocument();
    expect(screen.getByText("mssql")).toBeInTheDocument();
    expect(screen.getByText("dbo")).toBeInTheDocument();
    expect(screen.getByText("create table crm(id int);")).toBeInTheDocument();
  });

  it("renders projectResources as a read-only textarea", () => {
    render(
      <ProjectDetailView
        project={{
          ...active,
          projectResources: "== PROD ==\nHost/IP: 10.0.0.1",
        }}
      />,
    );

    const resources = screen.getByRole("textbox", { name: "Project Resources" });
    expect(resources).toHaveAttribute("readonly");
    expect(resources).toHaveValue("== PROD ==\nHost/IP: 10.0.0.1");
  });

  it("renders placeholder when projectResources is null", () => {
    render(<ProjectDetailView project={{ ...active, projectResources: null }} />);

    expect(screen.getByRole("textbox", { name: "Project Resources" })).toHaveValue("");
  });

  it("renders the lifecycle timeline", () => {
    render(<ProjectDetailView project={active} />);

    expect(screen.getByText("Lifecycle timeline")).toBeInTheDocument();
    expect(screen.getByText("Implementation", { selector: "p span" })).toBeInTheDocument();
    expect(screen.getByText("2026-06-29", { selector: "div span" })).toBeInTheDocument();
  });

  it("renders archived metadata when archived", () => {
    render(<ProjectDetailView project={archived} />);

    expect(screen.getByText("archived", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText(/2026-06-30/)).toBeInTheDocument();
  });

  it("renders the model policy section with effective values and sources", () => {
    render(
      <ProjectDetailView
        modelDefaults={modelDefaults}
        project={{
          ...active,
          modelPolicy: {
            fieldMapping: "field-model",
          },
        }}
      />,
    );

    expect(screen.getByText("Model Policy")).toBeInTheDocument();
    expect(screen.getByText("Field mapping model")).toBeInTheDocument();
    expect(screen.getByText("field-model")).toBeInTheDocument();
    expect(screen.getByText("planning-model")).toBeInTheDocument();
    expect(screen.getByText("Source: project override")).toBeInTheDocument();
    expect(screen.getAllByText("Source: engine.yaml").length).toBeGreaterThan(0);
  });
});
