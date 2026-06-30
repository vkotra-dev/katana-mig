import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Gate1Page from "./page";

const {
  approveGateMock,
  getGate1EvidenceMock,
  getGateStatusMock,
  loadUiSessionMock,
  rejectGateMock,
  paramsMock,
  searchParamsMock,
} = vi.hoisted(() => ({
  approveGateMock: vi.fn(),
  getGate1EvidenceMock: vi.fn(),
  getGateStatusMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
  rejectGateMock: vi.fn(),
  paramsMock: vi.fn(),
  searchParamsMock: vi.fn(),
}));

vi.mock("../../../../components/Topbar", () => ({
  Topbar: () => <div data-testid="topbar" />,
}));

vi.mock("../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../lib/gates-api", () => ({
  approveGate: approveGateMock,
  getGate1Evidence: getGate1EvidenceMock,
  getGateStatus: getGateStatusMock,
  rejectGate: rejectGateMock,
}));

vi.mock("next/navigation", () => ({
  useParams: () => paramsMock(),
  useSearchParams: () => ({
    get: searchParamsMock,
  }),
}));

describe("Gate1Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    paramsMock.mockReturnValue({ id: "run-1" });
    searchParamsMock.mockImplementation((key: string) => (key === "projectId" ? "project-1" : null));
    getGateStatusMock.mockResolvedValue({
      runId: "run-1",
      gate1: null,
      gate2: null,
    });
    getGate1EvidenceMock.mockResolvedValue({
      runId: "run-1",
      destinationObjectName: "Customer",
      mappingSnapshotVersion: "v1",
      fieldBindings: [
        { sourceField: "status_code", destinationField: "status", lookupName: "status_map" },
      ],
      piiFields: ["email"],
      coverageGaps: ["notes"],
    });
    approveGateMock.mockResolvedValue({
      runId: "run-1",
      gate1: { gate: "gate_1", decision: "approved", approverUserId: "user-1", decidedAt: "2026-06-30T00:00:00Z", notes: "OK" },
      gate2: null,
    });
    rejectGateMock.mockResolvedValue({
      runId: "run-1",
      gate1: null,
      gate2: null,
    });
  });

  it("renders evidence and submits an approval", async () => {
    render(<Gate1Page />);

    expect(await screen.findByText("Gate 1 Review")).toBeInTheDocument();
    expect(screen.getByText("Domain object map")).toBeInTheDocument();
    expect(screen.getByText("PII classification")).toBeInTheDocument();
    expect(screen.getByText("Coverage gaps")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Push back" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(approveGateMock).toHaveBeenCalledWith("token-1", "project-1", "run-1", "gate_1", { notes: "" }),
    );
  });

  it("requires structured push back fields", async () => {
    render(<Gate1Page />);

    expect(await screen.findByText("Gate 1 Review")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Push back" }));
    fireEvent.click(screen.getByRole("button", { name: "Submit push back" }));

    expect(screen.getByText("Affected objects and required changes are required.")).toBeInTheDocument();
  });
});
