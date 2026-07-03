import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DryRunPage from "./page";

const {
  loadUiSessionMock,
  getDryRunArtifactMock,
  approveDryRunMock,
  pushBackDryRunMock,
  pushMock,
} = vi.hoisted(() => ({
  loadUiSessionMock: vi.fn(),
  getDryRunArtifactMock: vi.fn(),
  approveDryRunMock: vi.fn(),
  pushBackDryRunMock: vi.fn(),
  pushMock: vi.fn(),
}));

vi.mock("../../../../../../components/Topbar", () => ({
  Topbar: () => <div>Topbar</div>,
}));

vi.mock("../../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../../lib/runs-api", () => ({
  getDryRunArtifact: getDryRunArtifactMock,
  approveDryRun: approveDryRunMock,
  pushBackDryRun: pushBackDryRunMock,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "project-1", run_id: "run-1" }),
  useRouter: () => ({ push: pushMock }),
}));

const SESSION = {
  accessToken: "token-1",
  expiresAt: "2026-07-02T12:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-1",
};

const ARTIFACT = {
  dryRunArtifactId: "dra-1",
  runId: "run-1",
  projectId: "project-1",
  destinationObjectName: "customers",
  successCount: 1840,
  failureCount: 2,
  fieldCoveragePct: 94.3,
  piiFields: [{ field: "SURNAME", token: "EMAIL_XXXX" }],
  sampleRows: [
    {
      source: { CUST_ID: "100042", SURNAME: "EMAIL_XXXX" },
      mapped: { customer_id: "100042", last_name: "EMAIL_XXXX" },
    },
  ],
  failures: [{ rowIndex: 141, reason: "unmapped_lookup", field: "ACCT_TYPE", value: "RETD" }],
  pushBackComment: null,
  status: "pending" as const,
  createdAt: "2026-07-01T10:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  loadUiSessionMock.mockReturnValue(SESSION);
  getDryRunArtifactMock.mockResolvedValue(ARTIFACT);
  approveDryRunMock.mockResolvedValue({
    run_id: "run-1",
    project_id: "project-1",
    status: "queued",
  });
  pushBackDryRunMock.mockResolvedValue({
    run_id: "run-1",
    project_id: "project-1",
    status: "dry_run_review",
  });
});

describe("DryRunPage", () => {
  it("renders the summary panel with counts and coverage", async () => {
    render(<DryRunPage />);

    expect(await screen.findByText("1,840")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText(/94\.3/)).toBeInTheDocument();
  });

  it("renders the PII masking status panel", async () => {
    render(<DryRunPage />);

    expect(await screen.findAllByText("SURNAME")).toHaveLength(2);
    expect(screen.getAllByText("EMAIL_XXXX").length).toBeGreaterThan(0);
  });

  it("renders sample rows table with source and mapped values", async () => {
    render(<DryRunPage />);

    expect(await screen.findByText("customer_id")).toBeInTheDocument();
    expect(screen.getByText("last_name")).toBeInTheDocument();
  });

  it("renders the failures list", async () => {
    render(<DryRunPage />);

    expect(await screen.findByText(/Row 141/i)).toBeInTheDocument();
    expect(screen.getByText("unmapped_lookup")).toBeInTheDocument();
    expect(screen.getByText("ACCT_TYPE")).toBeInTheDocument();
    expect(screen.getByText("RETD")).toBeInTheDocument();
  });

  it("approves and redirects to project overview", async () => {
    render(<DryRunPage />);

    const approveButton = await screen.findByRole("button", { name: /approve/i });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(approveDryRunMock).toHaveBeenCalledWith("token-1", "project-1", "run-1");
    });
    expect(pushMock).toHaveBeenCalledWith("/projects/project-1");
  });

  it("submits push-back comment and redirects to project overview", async () => {
    render(<DryRunPage />);

    await screen.findByRole("button", { name: /approve/i });

    const textarea = screen.getByPlaceholderText(/explain what needs to change/i);
    fireEvent.change(textarea, { target: { value: "Row 142 maps RETD to wrong destination." } });
    fireEvent.click(screen.getByRole("button", { name: /push back/i }));

    await waitFor(() => {
      expect(pushBackDryRunMock).toHaveBeenCalledWith(
        "token-1",
        "project-1",
        "run-1",
        "Row 142 maps RETD to wrong destination.",
      );
    });
    expect(pushMock).toHaveBeenCalledWith("/projects/project-1");
  });

  it("disables push-back button when comment is empty", async () => {
    render(<DryRunPage />);

    await screen.findByRole("button", { name: /approve/i });
    const pushBackButton = screen.getByRole("button", { name: /push back/i });
    expect(pushBackButton).toBeDisabled();
  });

  it("shows error when approve fails", async () => {
    approveDryRunMock.mockRejectedValue(new Error("Network error"));
    render(<DryRunPage />);

    const approveButton = await screen.findByRole("button", { name: /approve/i });
    fireEvent.click(approveButton);

    expect(await screen.findByRole("alert")).toHaveTextContent("Network error");
  });

  it("shows loading state before artifact loads", async () => {
    getDryRunArtifactMock.mockImplementation(
      () => new Promise<never>(() => undefined),
    );
    render(<DryRunPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
