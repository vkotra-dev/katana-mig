import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationBell } from "../NotificationBell";

const { listNotificationsMock, getUnreadCountMock, markNotificationReadMock, markAllReadMock, loadUiSessionMock } = vi.hoisted(() => ({
  listNotificationsMock: vi.fn(),
  getUnreadCountMock: vi.fn(),
  markNotificationReadMock: vi.fn(),
  markAllReadMock: vi.fn(),
  loadUiSessionMock: vi.fn(),
}));

vi.mock("../../../lib/session", () => ({
  loadUiSession: loadUiSessionMock,
}));

vi.mock("../../../lib/notifications-api", () => ({
  listNotifications: listNotificationsMock,
  getUnreadNotificationCount: getUnreadCountMock,
  markNotificationRead: markNotificationReadMock,
  markAllNotificationsRead: markAllReadMock,
}));

beforeEach(() => {
  vi.useRealTimers();
  listNotificationsMock.mockReset();
  getUnreadCountMock.mockReset();
  markNotificationReadMock.mockReset();
  markAllReadMock.mockReset();
  loadUiSessionMock.mockReset();
});

describe("NotificationBell", () => {
  it("renders the unread badge and polls the count", async () => {
    vi.useFakeTimers();
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-07-03T00:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    getUnreadCountMock.mockResolvedValue(2);

    render(<NotificationBell />);

    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByTestId("notification-badge")).toHaveTextContent("2");
    expect(getUnreadCountMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(30_000);
      await Promise.resolve();
    });
    expect(getUnreadCountMock).toHaveBeenCalledTimes(2);
  });

  it("opens a dropdown with notification links and mark actions", async () => {
    loadUiSessionMock.mockReturnValue({
      accessToken: "token-1",
      expiresAt: "2026-07-03T00:00:00Z",
      role: "central_team",
      sessionVersion: 1,
      userId: "user-1",
    });
    getUnreadCountMock.mockResolvedValue(1);
    listNotificationsMock.mockResolvedValue([
      {
        notificationId: "notification-1",
        userId: "user-1",
        projectId: "project-1",
        eventType: "gate_1_waiting",
        deepLink: "/projects/project-1/runs/run-1",
        read: false,
        payload: { run_id: "run-1" },
        readAt: null,
        createdAt: "2026-07-03T00:00:00Z",
      },
    ]);
    markNotificationReadMock.mockResolvedValue({
      notificationId: "notification-1",
      userId: "user-1",
      projectId: "project-1",
      eventType: "gate_1_waiting",
      deepLink: "/projects/project-1/runs/run-1",
      read: true,
      payload: { run_id: "run-1" },
      readAt: "2026-07-03T00:00:00Z",
      createdAt: "2026-07-03T00:00:00Z",
    });
    markAllReadMock.mockResolvedValue({ markedCount: 1 });

    render(<NotificationBell />);
    await screen.findByTestId("notification-badge");

    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(await screen.findByTestId("notification-list")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /gate 1/i })).toHaveAttribute(
      "href",
      "/projects/project-1/runs/run-1",
    );

    fireEvent.click(screen.getByRole("button", { name: "Mark read" }));
    await waitFor(() => expect(markNotificationReadMock).toHaveBeenCalledWith("token-1", "notification-1"));

    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));
    await waitFor(() => expect(markAllReadMock).toHaveBeenCalledWith("token-1"));
  });
});
