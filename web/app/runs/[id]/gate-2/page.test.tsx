import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Gate2Page from "./page";

const {
  approveGateMock,
  getGate2EvidenceMock,
  getGateStatusMock,
  loadUiSessionMock,
  paramsMock,
  searchParamsMock,
} = vi.hoisted(() => ({
  approveGateMock: vi.fn(),
  getGate2EvidenceMock: vi.fn(),
  getGateStatusMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
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
  getGate2Evidence: getGate2EvidenceMock,
  getGateStatus: getGateStatusMock,
  rejectGate: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => paramsMock(),
  useSearchParams: () => ({
    get: searchParamsMock,
  }),
}));

describe("Gate2Page", () => {
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
      gate1: { gate: "gate_1", decision: "approved", approverUserId: "user-1", decidedAt: "2026-06-30T00:00:00Z", notes: "OK" },
      gate2: null,
    });
    getGate2EvidenceMock.mockResolvedValue({
      runId: "run-1",
      lookupName: "status_map",
      rows: [
        { sourceValue: "A", destinationValue: "ACTIVE", state: "confirmed" },
        { sourceValue: "B", destinationValue: "MISSING", state: "unmapped" },
      ],
      confirmedCount: 1,
      unmappedCount: 1,
    });
    approveGateMock.mockResolvedValue({
      runId: "run-1",
      gate1: { gate: "gate_1", decision: "approved", approverUserId: "user-1", decidedAt: "2026-06-30T00:00:00Z", notes: "OK" },
      gate2: { gate: "gate_2", decision: "approved", approverUserId: "user-1", decidedAt: "2026-06-30T00:00:00Z", notes: "OK" },
    });
  });

  it("renders the dense lookup table and blocks submit while unmapped", async () => {
    render(<Gate2Page />);

    expect(await screen.findByText("Gate 2 Review")).toBeInTheDocument();
    expect(screen.getByText("Lookup rows")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit for approval" })).toBeDisabled();
    expect(screen.getByText("1 unmapped values must be resolved.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Override" })).toHaveLength(2);
  });

  it("opens the override editor for a row", async () => {
    render(<Gate2Page />);

    expect(await screen.findByText("Gate 2 Review")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Override" })[0]);

    expect(screen.getByLabelText("Override value")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Override value"), { target: { value: "ARCHIVED" } });
    fireEvent.click(screen.getByRole("button", { name: "Save override" }));

    await waitFor(() => expect(screen.getByText("Override saved.")).toBeInTheDocument());
  });
});
