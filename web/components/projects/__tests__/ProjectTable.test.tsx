import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectTable } from "../ProjectTable";
import type { ProjectRecord } from "../../../lib/projects-api";

const activeProject: ProjectRecord = {
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
    destinationSchemaDdl: null,
    environments: ["dev", "prod"],
  },
  lexiconScope: null,
  status: "active",
  createdAt: "2026-06-30T00:00:00Z",
  updatedAt: "2026-06-30T00:00:00Z",
  archivedAt: null,
};

const archivedProject: ProjectRecord = {
  ...activeProject,
  projectId: "project-2",
  name: "Beta Migration",
  status: "archived",
  archivedAt: "2026-06-30T12:00:00Z",
};

describe("ProjectTable", () => {
  it("renders projects with status and metadata", () => {
    render(<ProjectTable projects={[activeProject, archivedProject]} role="central_team" />);

    expect(screen.getByText("Alpha Migration")).toBeInTheDocument();
    expect(screen.getByText("Beta Migration")).toBeInTheDocument();
    expect(screen.getAllByText("GDPR")).toHaveLength(2);
    expect(screen.getAllByText("2026-06-30")).toHaveLength(2);
    expect(screen.getByText("archived", { selector: "span" })).toBeInTheDocument();
  });

  it("shows initiate project only for non-auditors", () => {
    const onInitiate = vi.fn();
    render(<ProjectTable projects={[]} role="central_team" onInitiate={onInitiate} />);

    fireEvent.click(screen.getByRole("button", { name: /initiate project/i }));

    expect(onInitiate).toHaveBeenCalledOnce();
  });

  it("hides initiate project for auditors", () => {
    render(<ProjectTable projects={[]} role="read_only_auditor" onInitiate={vi.fn()} />);

    expect(screen.queryByRole("button", { name: /initiate project/i })).not.toBeInTheDocument();
  });

  it("renders an empty state when no projects are available", () => {
    render(<ProjectTable projects={[]} role="project_stakeholder" />);

    expect(screen.getByText(/no projects/i)).toBeInTheDocument();
  });
});
