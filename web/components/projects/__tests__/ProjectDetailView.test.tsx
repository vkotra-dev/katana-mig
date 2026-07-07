import { fireEvent, render, screen } from "@testing-library/react";
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

  it("renders detail view with same field labels as edit", () => {
    render(<ProjectDetailView project={active} />);

    expect(screen.getByText("Target database engine")).toBeInTheDocument();
    expect(screen.getByText("Staging schema")).toBeInTheDocument();
    expect(screen.getByText("Destination schema")).toBeInTheDocument();
    expect(screen.getByText("Dry run")).toBeInTheDocument();
    expect(screen.getByText("Destination schema DDL")).toBeInTheDocument();
    expect(screen.getByText("Sample policy")).toBeInTheDocument();
  });

  it("renders projectResources HTML as formatted content", () => {
    render(
      <ProjectDetailView
        project={{
          ...active,
          projectResources: "<p><strong>PROD</strong></p><ul><li>Host: 10.0.0.1</li></ul>",
        }}
      />,
    );
    // The rendered HTML should contain the formatted elements, not raw markup
    expect(screen.getByText("PROD")).toBeInTheDocument();
    expect(screen.getByText("Host: 10.0.0.1")).toBeInTheDocument();
  });

  it("renders nothing for projectResources when null", () => {
    render(<ProjectDetailView project={{ ...active, projectResources: null }} />);
    expect(screen.queryByLabelText("Project Resources")).not.toBeInTheDocument();
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

  it("handles collapsible destination schema DDL", () => {
    const longDdl = "line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7";
    const projectWithLongDdl = {
      ...active,
      domainConfig: {
        ...active.domainConfig!,
        destinationSchemaDdl: longDdl,
      },
    };

    render(<ProjectDetailView project={projectWithLongDdl} />);

    expect(screen.getByText((content) => content.includes("line 1") && content.includes("...") && !content.includes("line 6"))).toBeInTheDocument();

    const button = screen.getByRole("button", { name: "Read more" });
    fireEvent.click(button);

    expect(screen.getByText((content) => content.includes("line 1") && content.includes("line 6") && content.includes("line 7"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Read less" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Read less" }));
    expect(screen.getByText((content) => content.includes("line 1") && content.includes("...") && !content.includes("line 6"))).toBeInTheDocument();
  });
});
