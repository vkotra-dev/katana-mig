import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PortfolioTable } from "./PortfolioTable";
import type { ProjectRecord } from "../../lib/projects-api";

function makeProject(overrides: Partial<ProjectRecord>): ProjectRecord {
  return {
    projectId: "project-1",
    name: "Alpha Migration",
    goal: "Move customer data into the new platform",
    repos: null,
    workspace: null,
    environment: null,
    executionEnvironments: ["dev", "prod"],
    modelPolicy: null,
    canonicalTerms: null,
    constraints: null,
    unresolvedQuestions: null,
    assumptions: null,
    domainConfig: {
      targetDbEngine: "postgresql",
      stagingSchema: null,
      dryRun: false,
      samplePolicy: null,
      destinationSchemaDdl: null,
      environments: ["dev", "prod"],
    },
    lexiconScope: null,
    status: "active",
    createdAt: "2026-06-01T00:00:00Z",
    updatedAt: "2026-06-30T09:15:00Z",
    archivedAt: null,
    ...overrides,
  };
}

const projects: ProjectRecord[] = [
  makeProject({
    projectId: "project-1",
    name: "Alpha Migration",
    status: "active",
    executionEnvironments: ["dev", "prod"],
    updatedAt: "2026-06-29T09:15:00Z",
  }),
  makeProject({
    projectId: "project-2",
    name: "Beta Warehouse",
    status: "archived",
    executionEnvironments: ["uat"],
    updatedAt: "2026-06-30T09:15:00Z",
  }),
  makeProject({
    projectId: "project-3",
    name: "Gamma Sync",
    status: "active",
    executionEnvironments: ["dev"],
    updatedAt: "2026-05-15T09:15:00Z",
  }),
];

describe("PortfolioTable", () => {
  it("defaults to active projects and shows the initiate action for central team", () => {
    const onInitiate = vi.fn();
    render(<PortfolioTable onInitiate={onInitiate} projects={projects} role="central_team" />);

    expect(screen.getByRole("button", { name: "Initiate project" })).toBeInTheDocument();
    expect(screen.getByText("Alpha Migration")).toBeInTheDocument();
    expect(screen.getByText("Gamma Sync")).toBeInTheDocument();
    expect(screen.queryByText("Beta Warehouse")).not.toBeInTheDocument();
  });

  it("filters by status, search, and environment", () => {
    render(<PortfolioTable projects={projects} role="central_team" />);

    fireEvent.change(screen.getByRole("combobox", { name: "Filter by status" }), {
      target: { value: "all" },
    });
    fireEvent.change(screen.getByRole("searchbox", { name: "Search projects" }), {
      target: { value: "beta" },
    });
    expect(screen.getByText("Beta Warehouse")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search projects" }), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Filter by environment" }), {
      target: { value: "prod" },
    });

    expect(screen.getByText("Alpha Migration")).toBeInTheDocument();
    expect(screen.queryByText("Beta Warehouse")).not.toBeInTheDocument();
    expect(screen.queryByText("Gamma Sync")).not.toBeInTheDocument();
  });

  it("sorts by name and last updated", () => {
    render(<PortfolioTable projects={projects} role="central_team" />);

    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Alpha Migration");

    fireEvent.click(screen.getByRole("button", { name: "Project" }));
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Gamma Sync");

    fireEvent.change(screen.getByRole("combobox", { name: "Filter by status" }), {
      target: { value: "all" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Last Updated" }));
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Beta Warehouse");
  });

  it("hides initiate action for read only auditors", () => {
    render(<PortfolioTable projects={projects} role="read_only_auditor" />);
    expect(screen.queryByRole("button", { name: "Initiate project" })).not.toBeInTheDocument();
  });

  it("shows an empty state when filters remove every row", () => {
    render(<PortfolioTable projects={projects} role="central_team" />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search projects" }), {
      target: { value: "missing-project" },
    });

    expect(screen.getByText("No matching projects.")).toBeInTheDocument();
  });
});
