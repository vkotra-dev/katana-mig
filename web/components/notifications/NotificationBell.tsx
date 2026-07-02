"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getUnreadNotificationCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationRecord,
} from "../../lib/notifications-api";
import { loadUiSession } from "../../lib/session";

function formatTimestamp(value: string): string {
  return value.slice(0, 16).replace("T", " ");
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState<number | null>(null);
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const session = useMemo(() => loadUiSession(), []);

  useEffect(() => {
    if (!session) {
      return;
    }

    let active = true;
    const loadCount = async () => {
      try {
        const unreadCount = await getUnreadNotificationCount(session.accessToken);
        if (active) {
          setCount(unreadCount);
        }
      } catch {
        if (active) {
          setCount(null);
        }
      }
    };

    void loadCount();
    const timer = window.setInterval(() => {
      void loadCount();
    }, 30_000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [session]);

  useEffect(() => {
    if (!open || !session) {
      return;
    }

    let active = true;
    setLoadingList(true);
    setErrorMessage(null);
    void listNotifications(session.accessToken)
      .then((items) => {
        if (active) {
          setNotifications(items);
        }
      })
      .catch((error) => {
        if (active) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load notifications.");
        }
      })
      .finally(() => {
        if (active) {
          setLoadingList(false);
        }
      });

    return () => {
      active = false;
    };
  }, [open, session]);

  const updateNotification = (notificationId: string, updated: NotificationRecord) => {
    setNotifications((current) => current.map((notification) => (notification.notificationId === notificationId ? updated : notification)));
    setCount((current) => (current === null ? current : Math.max(0, current - 1)));
  };

  const handleMarkRead = (notificationId: string) => {
    if (!session) {
      return;
    }

    void markNotificationRead(session.accessToken, notificationId)
      .then((updated) => {
        updateNotification(notificationId, updated);
      })
      .catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : "Unable to update notification.");
      });
  };

  const handleMarkAllRead = () => {
    if (!session) {
      return;
    }

    void markAllNotificationsRead(session.accessToken)
      .then((result) => {
        if (result.markedCount > 0) {
          setNotifications((current) => current.map((notification) => ({ ...notification, read: true })));
          setCount(0);
        }
      })
      .catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : "Unable to update notifications.");
      });
  };

  if (!session) {
    return null;
  }

  return (
    <div className="relative">
      <button
        aria-expanded={open}
        aria-label="Notifications"
        className="relative flex h-9 w-9 items-center justify-center rounded-full border border-outline-variant bg-surface text-slate-700 transition hover:bg-surface-container"
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span aria-hidden="true">🔔</span>
        {count !== null && count > 0 ? (
          <span
            data-testid="notification-badge"
            className="absolute -right-1 -top-1 min-w-5 rounded-full bg-amber-200 px-1.5 py-0.5 text-[11px] font-semibold text-amber-950"
          >
            {count}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          className="absolute right-0 top-11 z-40 w-[22rem] overflow-hidden rounded-2xl border border-outline-variant bg-surface-container shadow-xl"
          data-testid="notification-list"
        >
          <div className="flex items-center justify-between border-b border-outline-variant px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-slate-900">Notifications</div>
              <div className="text-xs text-slate-500">{count ?? 0} unread</div>
            </div>
            <button
              className="rounded-md border border-outline-variant px-3 py-1.5 text-xs font-semibold text-slate-700"
              onClick={handleMarkAllRead}
              type="button"
            >
              Mark all read
            </button>
          </div>

          {errorMessage ? (
            <div role="alert" className="border-b border-outline-variant px-4 py-3 text-sm text-error">
              {errorMessage}
            </div>
          ) : null}

          <div className="max-h-96 overflow-auto">
            {loadingList ? (
              <div className="px-4 py-6 text-sm text-slate-500">Loading notifications...</div>
            ) : notifications.length === 0 ? (
              <div className="px-4 py-8 text-sm text-slate-500">No notifications</div>
            ) : (
              notifications.map((notification) => (
                <div
                  key={notification.notificationId}
                  className={`border-b border-outline-variant px-4 py-3 text-sm ${notification.read ? "bg-surface" : "bg-amber-50"}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <a className="font-semibold text-slate-900 hover:underline" href={notification.deepLink}>
                        {notification.eventType}
                      </a>
                      <div className="mt-1 text-xs text-slate-500">{formatTimestamp(notification.createdAt)}</div>
                    </div>
                    {!notification.read ? (
                      <button
                        className="rounded-md border border-outline-variant px-2 py-1 text-xs font-semibold text-slate-700"
                        onClick={() => handleMarkRead(notification.notificationId)}
                        type="button"
                      >
                        Mark read
                      </button>
                    ) : (
                      <span className="text-xs text-slate-500">Read</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
