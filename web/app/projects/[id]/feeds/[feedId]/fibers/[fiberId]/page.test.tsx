import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FiberDetailPage from "./page";

const {
  getFiberMock,
  assignFiberMock,
  approveFiberMock,
  triggerFiberMock,
  loadUiSessionMock,
  topbarMock,
  backMock,
} = vi.hoisted(() => ({
  getFiberMock: vi.fn(),
  assignFiberMock: vi.fn(),
  approveFiberMock: vi.fn(),
  triggerFiberMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
  topbarMock: vi.fn(),
  backMock: vi.fn(),
}));

vi.mock("../../../../../../../components/Topbar", () => ({
  Topbar: () => {
    topbarMock();
    return null;
  },
}));

vi.mock("../../../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../../../lib/feeds-api", () => ({
  getFiber: getFiberMock,
  assignFiber: assignFiberMock,
  approveFiber: approveFiberMock,
  triggerFiber: triggerFiberMock,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "project-1", feedId: "feed-1", fiberId: "fiber-1" }),
  useRouter: () => ({ back: backMock }),
}));

const SESSION_CENTRAL = {
  accessToken: "token-central",
  expiresAt: "2026-07-01T12:00:00Z",
  role: "central_team" as const,
  sessionVersion: 1,
  userId: "user-central",
};

const SESSION_STAKEHOLDER = {
  accessToken: "token-stakeholder",
  expiresAt: "2026-07-01T12:00:00Z",
  role: "project_stakeholder" as const,
  sessionVersion: 1,
  userId: "user-stakeholder",
};

const FIBER_MAPPED = {
  fiberId: "fiber-1",
  feedId: "feed-1",
  projectId: "project-1",
  fiberType: "domain_object" as const,
  fiberKey: "customer",
  status: "mapped",
  source: "auto" as const,
  proposedMappings: null,
  fieldBindings: [
    { sourceField: "cust_id", destinationField: "customer_id", lookupName: null },
    { sourceField: "cust_name", destinationField: "full_name", lookupName: null },
  ],
  outputSql: null,
  createdAt: "2026-07-01T00:00:00Z",
  updatedAt: "2026-07-01T00:00:00Z",
};

const FIBER_OPERATOR_ASSIGNED = { ...FIBER_MAPPED, status: "operator_assigned" };
const FIBER_BUSINESS_APPROVED = { ...FIBER_MAPPED, status: "business_approved" };
const FIBER_OPERATOR_TRIGGERED = { ...FIBER_MAPPED, status: "operator_triggered" };

const FIBER_LOOKUP_ASSIGNED = {
  ...FIBER_MAPPED,
  fiberType: "lookup" as const,
  fiberKey: "account_type",
  status: "operator_assigned",
  fieldBindings: null,
  proposedMappings: [{ sourceValue: "A", destValue: "Active" }],
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe("FiberDetailPage", () => {
  it("shows loading state while fetching fiber", () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockReturnValue(new Promise(() => {}));

    render(<FiberDetailPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows the fiber status badge after loading", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    expect(await screen.findByText("mapped")).toBeInTheDocument();
  });

  it("shows field_bindings table for domain_object fiber", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    expect(await screen.findByText("cust_id")).toBeInTheDocument();
    expect(screen.getByText("customer_id")).toBeInTheDocument();
    expect(screen.getByText("cust_name")).toBeInTheDocument();
    expect(screen.getByText("full_name")).toBeInTheDocument();
  });

  it("shows proposed_mappings for lookup fiber", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_LOOKUP_ASSIGNED);

    render(<FiberDetailPage />);

    expect(await screen.findByText(/proposed mappings/i)).toBeInTheDocument();
    expect(screen.getByText(/account_type/i)).toBeInTheDocument();
  });

  it("shows Assign for Review button for central_team when status=mapped", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    expect(await screen.findByRole("button", { name: /assign for review/i })).toBeInTheDocument();
  });

  it("calls assignFiber on Assign click and updates status", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);
    assignFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /assign for review/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(assignFiberMock).toHaveBeenCalledWith("token-central", "project-1", "feed-1", "fiber-1");
    });
    expect(await screen.findByText("operator_assigned")).toBeInTheDocument();
  });

  it("does NOT show Assign button for project_stakeholder", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    await screen.findByText("mapped");
    expect(screen.queryByRole("button", { name: /assign for review/i })).not.toBeInTheDocument();
  });

  it("does NOT show Assign button when status is not mapped", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);

    render(<FiberDetailPage />);

    await screen.findByText("operator_assigned");
    expect(screen.queryByRole("button", { name: /assign for review/i })).not.toBeInTheDocument();
  });

  it("shows Approve button for project_stakeholder when status=operator_assigned", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);

    render(<FiberDetailPage />);

    expect(await screen.findByRole("button", { name: /^approve$/i })).toBeInTheDocument();
  });

  it("calls approveFiber on Approve click and updates status", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);
    approveFiberMock.mockResolvedValue(FIBER_BUSINESS_APPROVED);

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /^approve$/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(approveFiberMock).toHaveBeenCalledWith(
        "token-stakeholder",
        "project-1",
        "feed-1",
        "fiber-1",
      );
    });
    expect(await screen.findByText("business_approved")).toBeInTheDocument();
  });

  it("does NOT show Approve button for central_team", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_ASSIGNED);

    render(<FiberDetailPage />);

    await screen.findByText("operator_assigned");
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it("does NOT show Approve button when status is not operator_assigned", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    await screen.findByText("mapped");
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it("shows Trigger button for central_team when status=business_approved", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_BUSINESS_APPROVED);

    render(<FiberDetailPage />);

    expect(await screen.findByRole("button", { name: /^trigger$/i })).toBeInTheDocument();
  });

  it("calls triggerFiber on Trigger click and updates status", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_BUSINESS_APPROVED);
    triggerFiberMock.mockResolvedValue(FIBER_OPERATOR_TRIGGERED);

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /^trigger$/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(triggerFiberMock).toHaveBeenCalledWith(
        "token-central",
        "project-1",
        "feed-1",
        "fiber-1",
      );
    });
    expect(await screen.findByText("operator_triggered")).toBeInTheDocument();
  });

  it("does NOT show Trigger button for project_stakeholder", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_STAKEHOLDER);
    getFiberMock.mockResolvedValue(FIBER_BUSINESS_APPROVED);

    render(<FiberDetailPage />);

    await screen.findByText("business_approved");
    expect(screen.queryByRole("button", { name: /^trigger$/i })).not.toBeInTheDocument();
  });

  it("does NOT show Trigger button when status is not business_approved", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);

    render(<FiberDetailPage />);

    await screen.findByText("mapped");
    expect(screen.queryByRole("button", { name: /^trigger$/i })).not.toBeInTheDocument();
  });

  it("shows no action button when status=operator_triggered", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_OPERATOR_TRIGGERED);

    render(<FiberDetailPage />);

    await screen.findByText("operator_triggered");
    expect(screen.queryByRole("button", { name: /assign for review/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^trigger$/i })).not.toBeInTheDocument();
  });

  it("shows error banner when fiber fetch fails", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockRejectedValue(new Error("network error"));

    render(<FiberDetailPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("shows error banner when assign action fails", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);
    assignFiberMock.mockRejectedValue(new Error("409: fiber_not_ready"));

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /assign for review/i });
    fireEvent.click(btn);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("disables action button while request is in-flight", async () => {
    loadUiSessionMock.mockReturnValue(SESSION_CENTRAL);
    getFiberMock.mockResolvedValue(FIBER_MAPPED);
    assignFiberMock.mockReturnValue(new Promise(() => {}));

    render(<FiberDetailPage />);

    const btn = await screen.findByRole("button", { name: /assign for review/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /assigning/i })).toBeDisabled();
    });
  });
});
