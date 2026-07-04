import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApprovalsInbox } from "../ApprovalsInbox";

vi.mock("../../../lib/feed-slice-approval-api", () => ({
  listPendingApprovals: vi.fn().mockResolvedValue([]),
  approveFeedSlice: vi.fn(),
  rejectFeedSlice: vi.fn(),
}));

describe("ApprovalsInbox", () => {
  it("shows the feed-slice approval heading", async () => {
    render(<ApprovalsInbox token="token-1" role="central_team" />);

    await waitFor(() => expect(screen.getByText("Approvals")).toBeInTheDocument());
    expect(screen.getByText("Pending feed slices that need a decision.")).toBeInTheDocument();
  });
});
