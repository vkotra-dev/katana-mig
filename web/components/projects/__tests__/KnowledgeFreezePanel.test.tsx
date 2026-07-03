import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { KnowledgeFreezePanel } from "../KnowledgeFreezePanel";

const TOKEN = "token-1";
const PROJECT_ID = "project-1";

const freezeRecords = [
  {
    run_id: "run-new",
    knowledge_freeze_version: "cga-new",
    destination_object_name: "Invoice",
    environment: "PROD",
    status: "completed",
    started_at: "2026-07-01T10:00:00Z",
    created_at: "2026-07-01T10:05:00Z",
  },
  {
    run_id: "run-old",
    knowledge_freeze_version: "cga-old",
    destination_object_name: "Customer",
    environment: "UAT",
    status: "completed",
    started_at: "2026-07-01T09:00:00Z",
    created_at: "2026-07-01T09:05:00Z",
  },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("KnowledgeFreezePanel", () => {
  it("loads and renders freeze history", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => freezeRecords,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<KnowledgeFreezePanel projectId={PROJECT_ID} token={TOKEN} />);

    expect(screen.getByText("Loading knowledge freezes...")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Knowledge-freeze history" })).toBeInTheDocument();
    expect(screen.getByText("Invoice")).toBeInTheDocument();
    expect(screen.getByText("Customer")).toBeInTheDocument();
    expect(screen.getByText("cga-new")).toBeInTheDocument();
    expect(screen.getByText("cga-old")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/projects/${PROJECT_ID}/knowledge-freezes`),
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("shows an empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [],
      }),
    );

    render(<KnowledgeFreezePanel projectId={PROJECT_ID} token={TOKEN} />);

    expect(await screen.findByText("No knowledge freezes yet.")).toBeInTheDocument();
  });

  it("shows an error state on load failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ error: { code: "forbidden", message: "Forbidden" } }),
      }),
    );

    render(<KnowledgeFreezePanel projectId={PROJECT_ID} token={TOKEN} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Forbidden");
  });
});
