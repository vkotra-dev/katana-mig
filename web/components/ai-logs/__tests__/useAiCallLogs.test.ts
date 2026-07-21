import { renderHook, waitFor, act } from "@testing-library/react";
import { useAiCallLogs } from "../../../hooks/useAiCallLogs";
import { listAiCallLogs } from "../../../lib/ai-calls-api";
import { vi, describe, it, expect, beforeEach } from "vitest";

vi.mock("../../../lib/ai-calls-api", () => ({
  listAiCallLogs: vi.fn(),
}));

describe("useAiCallLogs", () => {
  const projectId = "test-project";
  const options = { feature: "codegen" as const };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches logs on mount", async () => {
    const mockLogs = [
      { callId: "1", feature: "codegen", callType: "codegen", timestamp: "2026-01-01T00:00:00", compiledSystemPrompt: "s", compiledUserPrompt: "u", rawLlmResponse: "r" } as any,
    ];
    (listAiCallLogs as any).mockResolvedValue(mockLogs);

    const { result } = renderHook(() => useAiCallLogs("mock-token", projectId, options));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.logs).toEqual(mockLogs);
    expect(listAiCallLogs).toHaveBeenCalledWith("mock-token", projectId, expect.objectContaining({ feature: "codegen", offset: 0, limit: 50 }));
  });

  it("handles error state", async () => {
    (listAiCallLogs as any).mockRejectedValue(new Error("API error"));

    const { result } = renderHook(() => useAiCallLogs("mock-token", projectId, options));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("API error");
  });

  it("paginates via loadMore", async () => {
    const firstPage = Array.from({ length: 50 }, (_, i) => ({ callId: String(i) } as any));
    const secondPage = [{ callId: "51" } as any];
    
    (listAiCallLogs as any)
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(secondPage);

    const { result } = renderHook(() => useAiCallLogs("mock-token", projectId, options));

    await waitFor(() => expect(result.current.loading).toBe(false));
    
    await act(async () => { await result.current.loadMore(); });
    
    expect(result.current.logs).toEqual([...firstPage, ...secondPage]);
    expect(listAiCallLogs).toHaveBeenCalledWith("mock-token", projectId, expect.objectContaining({ offset: 50 }));
  });
});
