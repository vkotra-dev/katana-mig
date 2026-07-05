import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SourceList } from "../SourceList";

const { getSchemaAnalysisMock, triggerSchemaAnalysisMock } = vi.hoisted(() => ({
  getSchemaAnalysisMock: vi.fn(),
  triggerSchemaAnalysisMock: vi.fn(),
}));

vi.mock("../../../lib/feeds-api", () => ({
  listFeedContracts: vi.fn().mockResolvedValue([
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

vi.mock("../../../lib/codegen-api", () => ({
  getSchemaAnalysis: getSchemaAnalysisMock,
  triggerSchemaAnalysis: triggerSchemaAnalysisMock,
}));

const onFeedClickMock = vi.fn();
const baseProps = {
  projectId: "project-1",
  role: "central_team" as const,
  token: "token-1",
  onFeedClick: onFeedClickMock,
};

describe("SourceList", () => {
  beforeEach(() => {
    getSchemaAnalysisMock.mockReset();
    triggerSchemaAnalysisMock.mockReset();
    onFeedClickMock.mockReset();
  });

  it("shows the DDL analysis banner when sources exist but no analysis is available", async () => {
    getSchemaAnalysisMock.mockResolvedValue(null);

    render(<SourceList {...baseProps} destinationSchemaDdl="CREATE TABLE customers (id INT);" />);

    expect(await screen.findByText("Analyze your destination schema to enable dependency-ordered SQL delivery.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze DDL" })).toBeInTheDocument();
  });

  it("disables the analysis action when the project has no destination schema DDL", async () => {
    getSchemaAnalysisMock.mockResolvedValue(null);

    render(<SourceList {...baseProps} destinationSchemaDdl={null} />);

    const button = await screen.findByRole("button", { name: "Analyze DDL" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Set destination_schema_ddl on the project first");
  });

  it("keeps the banner and shows re-analyze button once analysis exists", async () => {
    getSchemaAnalysisMock.mockResolvedValue({
      analysisId: "analysis-1",
      projectId: "project-1",
      destinationObjectSequence: ["customers"],
      identifiedCount: 1,
      processedCount: 1,
      analyzedAt: "2026-06-30T00:00:00Z",
    });

    render(<SourceList {...baseProps} destinationSchemaDdl="CREATE TABLE customers (id INT);" />);

    expect(await screen.findByText("Customer Extract")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Re-analyze DDL" })).toBeInTheDocument();
    expect(await screen.findByText("Destination schema was last analyzed at 2026-06-30.")).toBeInTheDocument();
  });

  it("renders source rows and triggers click", async () => {
    getSchemaAnalysisMock.mockResolvedValue(null);

    render(<SourceList {...baseProps} destinationSchemaDdl="CREATE TABLE customers (id INT);" />);

    expect(await screen.findByText("Customer Extract")).toBeInTheDocument();
    expect(screen.getByText("CSV")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Feed" })).toBeInTheDocument();

    const openFeedButton = screen.getByRole("button", { name: "Open feed" });
    fireEvent.click(openFeedButton);
    expect(onFeedClickMock).toHaveBeenCalledWith("source-1");
  });

  it("hides add source for non-admin roles", async () => {
    getSchemaAnalysisMock.mockResolvedValue(null);

    render(<SourceList projectId="project-1" role="project_stakeholder" token="token-1" destinationSchemaDdl="CREATE TABLE customers (id INT);" onFeedClick={onFeedClickMock} />);

    await waitFor(() => expect(screen.getByText("Customer Extract")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Add Feed" })).not.toBeInTheDocument();
  });

  it("triggers analysis and updates the banner to re-analyze after success", async () => {
    getSchemaAnalysisMock.mockResolvedValue(null);
    triggerSchemaAnalysisMock.mockResolvedValue({
      analysisId: "analysis-1",
      projectId: "project-1",
      destinationObjectSequence: ["customers"],
      identifiedCount: 1,
      processedCount: 0,
      analyzedAt: "2026-06-30T00:00:00Z",
    });

    render(<SourceList {...baseProps} destinationSchemaDdl="CREATE TABLE customers (id INT);" />);

    await screen.findByText("Analyze your destination schema to enable dependency-ordered SQL delivery.");
    fireEvent.click(screen.getByRole("button", { name: "Analyze DDL" }));

    await waitFor(() => {
      expect(triggerSchemaAnalysisMock).toHaveBeenCalledWith("token-1", "project-1");
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Re-analyze DDL" })).toBeInTheDocument();
      expect(screen.getByText("Destination schema was last analyzed at 2026-06-30.")).toBeInTheDocument();
      expect(screen.queryByText("Analyze your destination schema to enable dependency-ordered SQL delivery.")).not.toBeInTheDocument();
    });
  });
});
