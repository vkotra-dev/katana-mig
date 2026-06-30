import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SourceList } from "../SourceList";

vi.mock("../../../lib/sources-api", () => ({
  listSourceContracts: vi.fn().mockResolvedValue([
    {
      sourceDefinitionId: "source-1",
      projectId: "project-1",
      sourceType: "csv",
      label: "Customer Extract",
      encoding: "utf-8",
      destinationObjectReferences: null,
      layoutInformation: null,
      copybookText: null,
      status: "declared",
      createdAt: "2026-06-30T00:00:00Z",
    },
  ]),
}));

describe("SourceList", () => {
  it("renders source rows", async () => {
    render(<SourceList projectId="project-1" role="central_team" token="token-1" />);

    expect(await screen.findByText("Customer Extract")).toBeInTheDocument();
    expect(screen.getByText("CSV")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Source" })).toBeInTheDocument();
  });

  it("hides add source for non-admin roles", async () => {
    render(<SourceList projectId="project-1" role="project_stakeholder" token="token-1" />);

    await waitFor(() => expect(screen.getByText("Customer Extract")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Add Source" })).not.toBeInTheDocument();
  });
});
