import { API_BASE_URL } from "./api-base";

export interface FeedSliceCommentRecord {
  commentId: string;
  sourceSliceId: string;
  userId: string;
  displayName: string | null;
  role: string;
  body: string;
  createdAt: string;
}

export class FeedSliceCommentsApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message || code);
    this.name = "FeedSliceCommentsApiError";
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
    try {
      const body = (await response.json()) as { error?: { code?: string; message?: string } };
      throw new FeedSliceCommentsApiError(
        body.error?.code ?? "api_error",
        body.error?.message ?? "api_error",
        response.status,
      );
    } catch (error) {
      if (error instanceof FeedSliceCommentsApiError) {
        throw error;
      }
      throw new FeedSliceCommentsApiError("api_error", await response.text(), response.status);
    }
  }

  return (await response.json()) as T;
}

function mapCommentResponse(raw: any): FeedSliceCommentRecord {
  return {
    commentId: raw.comment_id,
    sourceSliceId: raw.source_slice_id,
    userId: raw.user_id,
    displayName: raw.display_name,
    role: raw.role,
    body: raw.body,
    createdAt: raw.created_at,
  };
}

export async function listFeedSliceComments(
  token: string,
  projectId: string,
  feedId: string,
  sliceId: string,
): Promise<FeedSliceCommentRecord[]> {
  const raw = await requestJson<any[]>(
    `/projects/${projectId}/sources/${feedId}/slices/${sliceId}/comments`,
    { method: "GET", token },
  );
  return raw.map(mapCommentResponse);
}

export async function createFeedSliceComment(
  token: string,
  projectId: string,
  feedId: string,
  sliceId: string,
  body: string,
): Promise<FeedSliceCommentRecord> {
  const raw = await requestJson<any>(
    `/projects/${projectId}/sources/${feedId}/slices/${sliceId}/comments`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ body }),
    },
  );
  return mapCommentResponse(raw);
}
