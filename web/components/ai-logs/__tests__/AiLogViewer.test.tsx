import { render, screen, fireEvent } from "@testing-library/react";
import { AiLogViewer } from "../AiLogViewer";
import { useAiCallLogs } from "../../../hooks/useAiCallLogs";
import { vi, describe, it, expect, beforeEach } from "vitest";

vi.mock("../../../hooks/useAiCallLogs", () => ({
  useAiCallLogs: vi.fn(),
}));

const mockLogs = [
  {
    callId: "1",
    callType: "codegen",
    timestamp: "2026-01-01T00:00:00Z",
    compiledSystemPrompt: "system prompt 1",
    compiledUserPrompt: "user prompt 1",
    rawLlmResponse: "{}",
  },
  {
    callId: "2",
    callType: "feed_mapping",
    timestamp: "2026-01-01T00:01:00Z",
    compiledSystemPrompt: "system prompt 2",
    compiledUserPrompt: "user prompt 2",
    rawLlmResponse: "{}",
  },
];

describe("AiLogViewer", () => {
  const props = {
    projectId: "test-project",
    feature: "codegen" as const,
    emptyLabel: "No logs",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders empty state", () => {
    (useAiCallLogs as any).mockReturnValue({
      logs: [],
      loading: false,
      error: null,
      hasMore: false,
      loadMore: vi.fn(),
    });

    render(<AiLogViewer {...props} />);
    expect(screen.getByText("No logs")).toBeInTheDocument();
  });

  it("renders log table", () => {
    (useAiCallLogs as any).mockReturnValue({
      logs: mockLogs,
      loading: false,
      error: null,
      hasMore: false,
      loadMore: vi.fn(),
    });

    render(<AiLogViewer {...props} />);
    expect(screen.getByText("codegen")).toBeInTheDocument();
    expect(screen.getByText("feed_mapping")).toBeInTheDocument();
  });

  it("opens inspect modal and switches tabs", async () => {
    (useAiCallLogs as any).mockReturnValue({
      logs: mockLogs,
      loading: false,
      error: null,
      hasMore: false,
      loadMore: vi.fn(),
    });

    render(<AiLogViewer {...props} />);
    
    const inspectButtons = screen.getAllByText("Inspect");
    fireEvent.click(inspectButtons[0]);

    expect(screen.getByText("AI Call Log Details")).toBeInTheDocument();
    
    // Default tab is System Prompt
    expect(screen.getByText("system prompt 1")).toBeInTheDocument();

    // Switch to User Prompt
    fireEvent.click(screen.getByText("User Prompt"));
    expect(screen.getByText("user prompt 1")).toBeInTheDocument();

    // Switch to Raw JSON
    fireEvent.click(screen.getByText("Raw JSON"));
    // Since it's JSON.stringify, it might be slightly different but we check for content existence
    expect(screen.getByText(/\{/)).toBeInTheDocument();
  });

  it("shows loading state", () => {
    (useAiCallLogs as any).mockReturnValue({
      logs: [],
      loading: true,
      error: null,
      hasMore: false,
      loadMore: vi.fn(),
    });

    render(<AiLogViewer {...props} />);
    expect(screen.getByText("Loading logs...")).toBeInTheDocument();
  });

  it("shows error state", () => {
    (useAiCallLogs as any).mockReturnValue({
      logs: [],
      loading: false,
      error: "Failed to fetch",
      hasMore: false,
      loadMore: vi.fn(),
    });

    render(<AiLogViewer {...props} />);
    expect(screen.getByText("Failed to fetch")).toBeInTheDocument();
  });
});
