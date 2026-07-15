/**
 * feed-slice-comments-api.ts
 *
 * Thin helpers for slice-level discussion threads.
 *
 * Architecture note: after migration 0029 (`unify_comments`), slice-level
 * comments live in the same `feed_comments` table as feed-level comments,
 * distinguished by the optional `source_slice_id` FK. These helpers call the
 * same `/projects/{pid}/feeds/{fid}/comments` endpoint that `feeds-api.ts`
 * uses for feed-level comments, but always pass `source_slice_id` in the
 * request body and filter to slice comments on read.
 */
import { API_BASE_URL } from "./api-base";

export interface FeedSliceCommentRecord {
  commentId: string;
  feedId: string;
  userId: string;
  displayName: string | null;
  role: string;
  body: string;
  createdAt: string;
  sourceSliceId: string;
  sourceSliceVersion: string | null;
}

function mapComment(raw: Record<string, unknown>): FeedSliceCommentRecord {
  return {
    commentId: raw.comment_id as string,
    feedId: raw.feed_id as string,
    userId: raw.user_id as string,
    displayName: (raw.display_name as string | null) ?? null,
    role: raw.role as string,
    body: raw.body as string,
    createdAt: raw.created_at as string,
    sourceSliceId: raw.source_slice_id as string,
    sourceSliceVersion: (raw.source_slice_version as string | null) ?? null,
  };
}

async function request<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error ${response.status}: ${text}`);
  }
  if (response.status === 204) return {} as T;
  return response.json() as Promise<T>;
}

/**
 * List all comments that are attached to a specific feed slice.
 * Fetches all feed comments and filters to those with a matching sourceSliceId.
 */
export async function listFeedSliceComments(
  token: string,
  projectId: string,
  feedId: string,
  sliceId: string,
): Promise<FeedSliceCommentRecord[]> {
  const all = await request<Record<string, unknown>[]>(
    `/projects/${projectId}/feeds/${feedId}/comments`,
    token,
  );
  return all
    .filter((c) => c.source_slice_id === sliceId)
    .map(mapComment);
}

/**
 * Post a new comment anchored to a specific feed slice.
 */
export async function createFeedSliceComment(
  token: string,
  projectId: string,
  feedId: string,
  sliceId: string,
  body: string,
): Promise<FeedSliceCommentRecord> {
  const raw = await request<Record<string, unknown>>(
    `/projects/${projectId}/feeds/${feedId}/comments`,
    token,
    {
      method: "POST",
      body: JSON.stringify({ body, source_slice_id: sliceId }),
    },
  );
  return mapComment(raw);
}
