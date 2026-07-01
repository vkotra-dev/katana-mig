import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ReconciliationPage from "./page";

const {
  exportReportMock,
  getLatestReportMock,
  getLineageMock,
  loadUiSessionMock,
  replaceMock,
  searchParamsMock,
  triggerReconciliationMock,
} = vi.hoisted(() => ({
  exportReportMock: vi.fn(),
  getLatestReportMock: vi.fn(),
  getLineageMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
  replaceMock: vi.fn(),
  searchParamsMock: vi.fn(),
  triggerReconciliationMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "run-1" }),
  useRouter: () => ({
    replace: replaceMock,
  }),
  useSearchParams: () => ({
    get: searchParamsMock,
  }),
}));

vi.mock("../../../../components/Topbar", () => ({
  Topbar: () => <div data-testid="topbar" />,
}));

vi.mock("../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../lib/reconciliation-api", () => ({
  exportReport: exportReportMock,
  getLatestReport: getLatestReportMock,
  getLineage: getLineageMock,
  triggerReconciliation: triggerReconciliationMock,
}));

const mockSession = {
  accessToken: "token-1",
  expiresAt: "2026-07-01T00:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-1",
};

const mockReport = {
  reportId: "report-1",
  runId: "run-1",
  checks: [
    { checkName: "key_integrity", status: "fail" as const, detail: "missing keys" },
    { checkName: "row_count", status: "pass" as const, detail: "counts match" },
  ],
  overallStatus: "fail" as const,
  rowCountSummary: {
    sourceRows: 2,
    destinationRows: 3,
    rejected: 1,
    duplicated: 0,
    partiallyMapped: 0,
  },
  createdAt: "2026-07-01T00:00:00Z",
  completedAt: "2026-07-01T00:05:00Z",
};

const mockLineage = {
  rows: [
    {
      lineageRowId: "lineage-1",
      sourceRowIndex: 0,
      sourceRowKey: "C001",
      destinationRowId: "D001",
      mappingRulesApplied: ["customer_id → customer_id"],
      outcome: "confirmed" as const,
      outcomeDetail: null,
    },
    {
      lineageRowId: "lineage-2",
      sourceRowIndex: 1,
      sourceRowKey: "C002",
      destinationRowId: null,
      mappingRulesApplied: ["status → status"],
      outcome: "rejected" as const,
      outcomeDetail: "no destination row produced.",
    },
    {
      lineageRowId: "lineage-3",
      sourceRowIndex: null,
      sourceRowKey: null,
      destinationRowId: "D003",
      mappingRulesApplied: ["customer_id → customer_id"],
      outcome: "rejected" as const,
      outcomeDetail: "orphaned mapped row — no source row at this index",
    },
  ],
  total: 3,
  offset: 0,
  limit: 100,
};

beforeEach(() => {
  vi.clearAllMocks();
  loadUiSessionMock.mockReturnValue(mockSession);
  searchParamsMock.mockImplementation((key: string) => (key === "projectId" ? "project-1" : null));
  getLatestReportMock.mockResolvedValue(mockReport);
  getLineageMock.mockResolvedValue(mockLineage);
  exportReportMock.mockResolvedValue({
    ...mockReport,
    exportedAt: "2026-07-01T00:06:00Z",
    lineageRows: mockLineage.rows,
  });
  triggerReconciliationMock.mockResolvedValue(mockReport);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ReconciliationPage", () => {
  it("renders the report with failed checks pinned first", async () => {
    render(<ReconciliationPage />);

    expect(await screen.findByText("Reconciliation & Lineage")).toBeInTheDocument();
    const checks = screen.getAllByRole("listitem");
    expect(checks[0]).toHaveTextContent("key integrity");
    expect(checks[0]).toHaveTextContent("fail");
    expect(screen.getByText("Source Rows")).toBeInTheDocument();
    expect(screen.getByText("Lineage Explorer")).toBeInTheDocument();
    expect(screen.getByText("Reconciliation failed")).toBeInTheDocument();
  });

  it("drills down by source row and destination row", async () => {
    render(<ReconciliationPage />);

    expect(await screen.findByRole("button", { name: "0" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "0" }));
    await waitFor(() =>
      expect(getLineageMock).toHaveBeenCalledWith("token-1", "project-1", "run-1", "report-1", {
        sourceRowIndex: 0,
      }),
    );

    expect(await screen.findByRole("button", { name: "D001" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "D001" }));
    await waitFor(() =>
      expect(getLineageMock).toHaveBeenCalledWith("token-1", "project-1", "run-1", "report-1", {
        destinationRowId: "D001",
      }),
    );
  });

  it("downloads the exported report", async () => {
    const createObjectURL = vi.fn(() => "blob:test");
    const revokeObjectURL = vi.fn();
    const click = vi.fn();
    const originalCreateElement = document.createElement.bind(document);

    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      if (tagName === "a") {
        return {
          click,
          href: "",
          download: "",
        } as unknown as HTMLElement;
      }
      return originalCreateElement(tagName);
    });

    render(<ReconciliationPage />);

    await screen.findByText("Download");
    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    await waitFor(() => {
      expect(exportReportMock).toHaveBeenCalledWith("token-1", "project-1", "run-1", "report-1");
    });
    expect(click).toHaveBeenCalled();
    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
  });

  it("shows missing project context and skips API calls", async () => {
    searchParamsMock.mockImplementation((key: string) => (key === "projectId" ? null : null));

    render(<ReconciliationPage />);

    expect(await screen.findByText("Missing project context.")).toBeInTheDocument();
    expect(getLatestReportMock).not.toHaveBeenCalled();
  });

  it("lets central team trigger reconciliation when no report exists", async () => {
    getLatestReportMock.mockRejectedValueOnce({ status: 404 });

    render(<ReconciliationPage />);

    expect(await screen.findByRole("button", { name: "Run reconciliation" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Run reconciliation" }));

    await waitFor(() => {
      expect(triggerReconciliationMock).toHaveBeenCalledWith("token-1", "project-1", "run-1");
    });
  });
});
