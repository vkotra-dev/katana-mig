import { API_BASE_URL } from "./api-base";

export interface NotificationRecord {
  notificationId: string;
  userId: string;
  projectId: string;
  eventType: string;
  deepLink: string;
  read: boolean;
  payload: Record<string, unknown> | null;
  readAt: string | null;
  createdAt: string;
}

export interface NotificationCountRecord {
  unreadCount: number;
}

export interface MarkAllNotificationsReadRecord {
  markedCount: number;
}

export class NotificationApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "NotificationApiError";
    this.code = code;
    this.status = status;
  }
}

function authHeaders(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

async function parseApiError(response: Response): Promise<NotificationApiError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    const code = body.error?.code ?? "api_error";
    const message = body.error?.message ?? code;
    return new NotificationApiError(code, message, response.status);
  } catch {
    const message = await response.text();
    return new NotificationApiError("api_error", message || "api_error", response.status);
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit & { token: string },
): Promise<T> {
  const { token, headers, ...rest } = init;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      ...authHeaders(token),
      ...(headers ?? {}),
    },
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function mapNotificationResponse(response: {
  notification_id: string;
  user_id: string;
  project_id: string;
  event_type: string;
  deep_link: string;
  read: boolean;
  payload: Record<string, unknown> | null;
  read_at: string | null;
  created_at: string;
}): NotificationRecord {
  return {
    notificationId: response.notification_id,
    userId: response.user_id,
    projectId: response.project_id,
    eventType: response.event_type,
    deepLink: response.deep_link,
    read: response.read,
    payload: response.payload,
    readAt: response.read_at,
    createdAt: response.created_at,
  };
}

export async function listNotifications(token: string): Promise<NotificationRecord[]> {
  const response = await requestJson<Array<Parameters<typeof mapNotificationResponse>[0]>>(
    "/notifications",
    { method: "GET", token },
  );
  return response.map(mapNotificationResponse);
}

export async function getUnreadNotificationCount(token: string): Promise<number> {
  const response = await requestJson<{ unread_count: number }>("/notifications/count", {
    method: "GET",
    token,
  });
  return response.unread_count;
}

export async function markNotificationRead(token: string, notificationId: string): Promise<NotificationRecord> {
  const response = await requestJson<Parameters<typeof mapNotificationResponse>[0]>(
    `/notifications/${notificationId}/read`,
    { method: "POST", token },
  );
  return mapNotificationResponse(response);
}

export async function markAllNotificationsRead(token: string): Promise<MarkAllNotificationsReadRecord> {
  const response = await requestJson<{ marked_count: number }>("/notifications/read-all", {
    method: "POST",
    token,
  });
  return { markedCount: response.marked_count };
}
