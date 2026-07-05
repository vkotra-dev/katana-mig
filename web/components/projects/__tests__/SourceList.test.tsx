import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SourceList } from "../SourceList";



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

const onFeedClickMock = vi.fn();
const baseProps = {
  projectId: "project-1",
  role: "central_team" as const,
  token: "token-1",
  onFeedClick: onFeedClickMock,
};

describe("SourceList", () => {
  beforeEach(() => {
    onFeedClickMock.mockReset();
  });

  it("renders source rows and triggers click", async () => {
    render(<SourceList {...baseProps} />);

    expect(await screen.findByText("Customer Extract")).toBeInTheDocument();
    expect(screen.getByText("CSV")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Feed" })).toBeInTheDocument();

    const openFeedButton = screen.getByRole("button", { name: "Open feed" });
    fireEvent.click(openFeedButton);
    expect(onFeedClickMock).toHaveBeenCalledWith("source-1");
  });

  it("hides add source for non-admin roles", async () => {
    render(<SourceList projectId="project-1" role="project_stakeholder" token="token-1" onFeedClick={onFeedClickMock} />);

    await waitFor(() => expect(screen.getByText("Customer Extract")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Add Feed" })).not.toBeInTheDocument();
  });
});
