import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SourceArtifactsPanel } from "../SourceArtifactsPanel";

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
      status: "active",
      createdAt: "2026-06-30T00:00:00Z",
    },
  ]),
  listFeedSlices: vi.fn().mockResolvedValue([]),
}));

vi.mock("../../../lib/feed-slice-approval-api", () => ({
  approveFeedSlice: vi.fn(),
  rejectFeedSlice: vi.fn(),
  resubmitFeedSlice: vi.fn(),
}));

describe("SourceArtifactsPanel", () => {
  it("shows feed-slice copy", async () => {
    render(<SourceArtifactsPanel projectId="project-1" token="token-1" role="central_team" />);

    await waitFor(() => expect(screen.getByText("Artifacts")).toBeInTheDocument());
    expect(screen.getByText("Feed slice versions and approval status.")).toBeInTheDocument();
    expect(screen.getByText("No feed slices yet.")).toBeInTheDocument();
  });
});
