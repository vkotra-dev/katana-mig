import { describe, expect, it } from "vitest";
import { clearUiSession, loadUiSession, saveUiSession } from "./session";

describe("session storage", () => {
  it("persists and restores the ui session", () => {
    clearUiSession();

    saveUiSession({
      accessToken: "token-abc",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "project_stakeholder",
      sessionVersion: 3,
      userId: "user-42",
    });

    expect(loadUiSession()).toEqual({
      accessToken: "token-abc",
      expiresAt: "2026-06-30T12:00:00Z",
      role: "project_stakeholder",
      sessionVersion: 3,
      userId: "user-42",
    });
  });
});
