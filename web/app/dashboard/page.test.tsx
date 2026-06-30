import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "./page";

const { pushMock, replaceMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: replaceMock,
  }),
}));

vi.mock("../../lib/session", () => ({
  loadUiSession: vi.fn(),
}));

vi.mock("../../lib/projects-api", () => ({
  listProjects: vi.fn(),
  projectErrorMessage: (error: unknown) => (error instanceof Error ? error.message : "Unable to load project."),
}));

vi.mock("../../lib/slice-approval-api", () => ({
  getPendingApprovalCount: vi.fn(),
}));

import { listProjects } from "../../lib/projects-api";
import { getPendingApprovalCount } from "../../lib/slice-approval-api";
import { loadUiSession } from "../../lib/session";
import { within } from "@testing-library/react";

const mockSession = {
  accessToken: "token-1",
  expiresAt: "2026-06-30T12:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-1",
};

const mockProject = {
  projectId: "project-1",
  name: "Alpha Migration",
  goal: "Move data",
  repos: null,
  workspace: null,
  environment: null,
  executionEnvironments: ["dev"],
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
    environments: ["dev"],
  },
  lexiconScope: null,
  status: "active" as const,
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-30T00:00:00Z",
  archivedAt: null,
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("DashboardPage", () => {
  it("shows loading state before the data resolves", () => {
    vi.mocked(loadUiSession).mockReturnValue(mockSession);
    vi.mocked(listProjects).mockReturnValue(new Promise(() => {}));
    vi.mocked(getPendingApprovalCount).mockReturnValue(new Promise(() => {}));

    render(<DashboardPage />);

    expect(screen.getByText("Loading portfolio...")).toBeInTheDocument();
  });

  it("renders the summary strip and project table on success", async () => {
    vi.mocked(loadUiSession).mockReturnValue(mockSession);
    vi.mocked(listProjects).mockResolvedValue([mockProject]);
    vi.mocked(getPendingApprovalCount).mockResolvedValue(3);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Total Projects")).toBeInTheDocument();
    });
    expect(screen.getByText("Alpha Migration")).toBeInTheDocument();
    const pendingCard = screen.getByText("Pending Approvals").parentElement;
    expect(pendingCard).not.toBeNull();
    expect(within(pendingCard as HTMLElement).getByText("3")).toBeInTheDocument();
  });

  it("renders an error banner when loading fails", async () => {
    vi.mocked(loadUiSession).mockReturnValue(mockSession);
    vi.mocked(listProjects).mockRejectedValue(new Error("server error"));
    vi.mocked(getPendingApprovalCount).mockResolvedValue(0);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toHaveTextContent("server error");
  });

  it("redirects to the login page when there is no session", async () => {
    vi.mocked(loadUiSession).mockReturnValue(null);

    render(<DashboardPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/");
    });
  });
});
