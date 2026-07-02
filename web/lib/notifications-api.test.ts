import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getUnreadNotificationCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "./notifications-api";

const BASE = "http://127.0.0.1:8000";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("notifications-api", () => {
  it("lists notifications with auth headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          notification_id: "notification-1",
          user_id: "user-1",
          project_id: "project-1",
          event_type: "gate_1_waiting",
          deep_link: "/projects/project-1/runs/run-1",
          read: false,
          payload: { run_id: "run-1" },
          read_at: null,
          created_at: "2026-07-03T00:00:00Z",
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await listNotifications("token-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/notifications`,
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result[0].notificationId).toBe("notification-1");
  });

  it("gets the unread count", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ unread_count: 4 }),
      }),
    );

    await expect(getUnreadNotificationCount("token-1")).resolves.toBe(4);
  });

  it("marks a notification as read", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        notification_id: "notification-1",
        user_id: "user-1",
        project_id: "project-1",
        event_type: "gate_1_waiting",
        deep_link: "/projects/project-1/runs/run-1",
        read: true,
        payload: null,
        read_at: "2026-07-03T00:00:00Z",
        created_at: "2026-07-03T00:00:00Z",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await markNotificationRead("token-1", "notification-1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/notifications/notification-1/read`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.read).toBe(true);
  });

  it("marks all notifications as read", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ marked_count: 2 }),
      }),
    );

    await expect(markAllNotificationsRead("token-1")).resolves.toEqual({ markedCount: 2 });
  });
});
