import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CrReviewPage from "./page";

const {
  getChangeRequestMock,
  resolveChangeRequestMock,
  loadUiSessionMock,
  pushMock,
  topbarMock,
} = vi.hoisted(() => ({
  getChangeRequestMock: vi.fn(),
  resolveChangeRequestMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
  pushMock: vi.fn(),
  topbarMock: vi.fn(),
}));

vi.mock("../../../../../components/Topbar", () => ({
  Topbar: () => {
    topbarMock();
    return null;
  },
}));

vi.mock("../../../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../../../lib/change-requests-api", () => ({
  getChangeRequest: getChangeRequestMock,
  resolveChangeRequest: resolveChangeRequestMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

const session = {
  accessToken: "token-1",
  expiresAt: "2026-07-02T00:00:00Z",
  role: "project_stakeholder",
  sessionVersion: 1,
  userId: "user-1",
};

const crDetail = {
  changeRequestId: "cr-1",
  projectId: "project-1",
  changeRequestType: "lookup_delta",
  status: "open",
  title: "Lookup delta for account_type",
  payload: {
    runId: "run-1",
    lookupName: "account_type",
    unmappedValue: "RETD",
    destinationObjectName: "customers",
  },
  createdAt: "2026-07-01T10:00:00Z",
  updatedAt: "2026-07-01T10:00:00Z",
};

describe("CrReviewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders CR detail fields after load", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockResolvedValue(crDetail);

    render(<CrReviewPage params={Promise.resolve({ id: "project-1", crId: "cr-1" })} />);

    expect(await screen.findByText("Lookup delta for account_type")).toBeInTheDocument();
    expect(screen.getByText("RETD")).toBeInTheDocument();
    expect(screen.getByText("customers")).toBeInTheDocument();
    expect(screen.getByText("run-1")).toBeInTheDocument();
    expect(getChangeRequestMock).toHaveBeenCalledWith("token-1", "project-1", "cr-1");
  });

  it("submits the accepted value and redirects to project overview on success", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockResolvedValue(crDetail);
    resolveChangeRequestMock.mockResolvedValue({
      changeRequestId: "cr-1",
      status: "resolved",
    });

    render(<CrReviewPage params={Promise.resolve({ id: "project-1", crId: "cr-1" })} />);

    const input = await screen.findByLabelText("Map this to:");
    fireEvent.change(input, { target: { value: "RETIRED" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(resolveChangeRequestMock).toHaveBeenCalledWith("token-1", "project-1", "cr-1", {
        acceptedValue: "RETIRED",
      }),
    );
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/projects/project-1"));
  });

  it("shows an error alert when resolve fails", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockResolvedValue(crDetail);
    resolveChangeRequestMock.mockRejectedValue(new Error("Already closed."));

    render(<CrReviewPage params={Promise.resolve({ id: "project-1", crId: "cr-1" })} />);

    const input = await screen.findByLabelText("Map this to:");
    fireEvent.change(input, { target: { value: "RETIRED" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Already closed.");
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("shows a load error when getChangeRequest fails", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockRejectedValue(new Error("Not found."));

    render(<CrReviewPage params={Promise.resolve({ id: "project-1", crId: "cr-1" })} />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Not found.");
  });

  it("disables submit while submitting", async () => {
    loadUiSessionMock.mockReturnValue(session);
    getChangeRequestMock.mockResolvedValue(crDetail);
    let resolvePromise!: (value: unknown) => void;
    resolveChangeRequestMock.mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve;
      }),
    );

    render(<CrReviewPage params={Promise.resolve({ id: "project-1", crId: "cr-1" })} />);

    const input = await screen.findByLabelText("Map this to:");
    fireEvent.change(input, { target: { value: "RETIRED" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();

    resolvePromise({ changeRequestId: "cr-1", status: "resolved" });
    await waitFor(() => expect(pushMock).toHaveBeenCalled());
  });
});
