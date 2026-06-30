import { describe, expect, it, vi } from "vitest";
import { login } from "./auth-api";

describe("login", () => {
  it("posts credentials to the auth API and maps the session response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: "token-123",
        token_type: "bearer",
        expires_at: "2026-06-30T12:00:00Z",
        session_version: 7,
        user: {
          user_id: "user-1",
          email: "operator@example.com",
          display_name: "Operator",
          role: "central_team",
          status: "active",
        },
      }),
    });

    vi.stubGlobal("fetch", fetchMock);

    const session = await login("operator@example.com", "secret-password");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/auth/login",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          email: "operator@example.com",
          password: "secret-password",
        }),
      })
    );
    expect(session.accessToken).toBe("token-123");
    expect(session.user.role).toBe("central_team");
    expect(session.sessionVersion).toBe(7);
  });
});
