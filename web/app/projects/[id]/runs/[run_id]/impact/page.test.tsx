import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ImpactPage from "./page";

const {
  loadUiSessionMock,
  getImpactReportMock,
  acknowledgeImpactMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getImpactReportMock: vi.fn(),
  acknowledgeImpactMock: vi.fn(),
}));

vi.mock("../../../../../../components/Topbar", () => ({
  Topbar: () => <div data-testid="topbar" />,
}));

vi.mock("../../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../../lib/runs-api", () => ({
  getImpactReport: getImpactReportMock,
  acknowledgeImpact: acknowledgeImpactMock,
}));

const mockRouterPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockRouterPush }),
}));

const STUB_REPORT = {
  runId: "run-1",
  gateRejection: {
    rejectedBy: "user-99",
    rejectedAt: "2026-07-01T10:00:00Z",
    affectedObjects: ["customers", "orders"],
    requiredChanges: "ACCT_TYPE lookup missing RETD. Remove LEGACY_CODE binding.",
    notes: null,
  },
  replayScope: ["run-abc", "run-def"],
  aiRecommendation: {
    recommendation: "Add RETD to account_type lookup and remove LEGACY_CODE from field bindings.",
    suggestedFix: "1. Open account_type lookup fiber and add RETD. 2. Remove LEGACY_CODE binding.",
    minimalReplayScope: ["customers"],
  },
};

describe("ImpactPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-07-02T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    getImpactReportMock.mockResolvedValue(STUB_REPORT);
    acknowledgeImpactMock.mockResolvedValue({
      run_id: "run-1",
      project_id: "project-1",
      status: "pending_gate_1",
    });
  });

  it("renders the three panels with report data", async () => {
    render(<ImpactPage params={Promise.resolve({ id: "project-1", run_id: "run-1" })} />);

    expect(await screen.findByText("Gate 1 Pushback")).toBeInTheDocument();
    expect(screen.getByText("Impact Review")).toBeInTheDocument();
    expect(screen.getByText("ACCT_TYPE lookup missing RETD. Remove LEGACY_CODE binding.")).toBeInTheDocument();
    expect(screen.getAllByText("customers")).toHaveLength(2);
    expect(screen.getByText("orders")).toBeInTheDocument();
    expect(screen.getByText("Replay Scope")).toBeInTheDocument();
    expect(screen.getByText("run-abc")).toBeInTheDocument();
    expect(screen.getByText("run-def")).toBeInTheDocument();
    expect(screen.getByText("AI Recommendation")).toBeInTheDocument();
    expect(
      screen.getByText("Add RETD to account_type lookup and remove LEGACY_CODE from field bindings."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("1. Open account_type lookup fiber and add RETD. 2. Remove LEGACY_CODE binding."),
    ).toBeInTheDocument();
  });

  it("renders the Acknowledge and fix button and Request clarification button", async () => {
    render(<ImpactPage params={Promise.resolve({ id: "project-1", run_id: "run-1" })} />);

    expect(await screen.findByText("Impact Review")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Acknowledge and fix" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request clarification" })).toBeInTheDocument();
  });

  it("Request clarification button is disabled", async () => {
    render(<ImpactPage params={Promise.resolve({ id: "project-1", run_id: "run-1" })} />);

    expect(await screen.findByText("Impact Review")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request clarification" })).toBeDisabled();
  });

  it("clicking Acknowledge and fix calls acknowledgeImpact and redirects", async () => {
    render(<ImpactPage params={Promise.resolve({ id: "project-1", run_id: "run-1" })} />);

    expect(await screen.findByText("Gate 1 Pushback")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Acknowledge and fix" }));

    await waitFor(() => expect(acknowledgeImpactMock).toHaveBeenCalledWith("token-1", "project-1", "run-1"));
    await waitFor(() => expect(mockRouterPush).toHaveBeenCalledWith("/runs/run-1?projectId=project-1"));
  });

  it("shows an error message when acknowledge fails", async () => {
    acknowledgeImpactMock.mockRejectedValue(new Error("Acknowledge failed."));

    render(<ImpactPage params={Promise.resolve({ id: "project-1", run_id: "run-1" })} />);

    expect(await screen.findByText("Gate 1 Pushback")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Acknowledge and fix" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Acknowledge failed.");
  });

  it("shows error when report fails to load", async () => {
    getImpactReportMock.mockRejectedValue(new Error("Gate 1 has not been rejected."));

    render(<ImpactPage params={Promise.resolve({ id: "project-1", run_id: "run-1" })} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Gate 1 has not been rejected.");
  });

  it("shows empty replay scope message when list is empty", async () => {
    getImpactReportMock.mockResolvedValue({
      ...STUB_REPORT,
      replayScope: [],
    });

    render(<ImpactPage params={Promise.resolve({ id: "project-1", run_id: "run-1" })} />);

    expect(await screen.findByText("No other runs are affected.")).toBeInTheDocument();
  });
});
