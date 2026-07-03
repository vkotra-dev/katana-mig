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
  environment: "PROD",
  executionEnvironments: ["STG", "UAT", "PROD"],
  modelPolicy: null,
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
      expect(onSubmit).toHaveBeenCalledWith({
        name: "CRM Migration v2",
        goal: "Migrate all CRM data",
        environment: "PROD",
        executionEnvironments: ["STG", "UAT", "PROD"],
        domainConfig: expect.any(Object),
      }),
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
