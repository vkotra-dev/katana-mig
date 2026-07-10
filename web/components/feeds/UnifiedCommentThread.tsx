"use client";

import { useEffect, useState } from "react";
import {
  createFeedComment,
  listFeedComments,
  type FeedCommentRecord,
} from "../../lib/feeds-api";

export interface UnifiedCommentThreadProps {
  projectId: string;
  feedId: string;
  sliceId?: string;
  token: string;
}

type UnifiedComment = {
  key: string;
  sourceSliceVersion: string | null;
  displayName: string | null;
  userId: string;
  role: string;
  body: string;
  createdAt: string;
};

function fromFeedComment(c: FeedCommentRecord): UnifiedComment {
  return {
    key: `feed-${c.commentId}`,
    sourceSliceVersion: c.sourceSliceVersion ?? null,
    displayName: c.displayName,
    userId: c.userId,
    role: c.role,
    body: c.body,
    createdAt: c.createdAt,
  };
}

function formatTimestamp(value: string): string {
  return value.replace("T", " ").slice(0, 16) + " UTC";
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset ring-outline-variant bg-surface text-slate-600">
      {role}
    </span>
  );
}

function SourceBadge({ version }: { version: string | null }) {
  return version ? (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200" data-testid="comment-version-badge">
      slice {version}
    </span>
  ) : (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200" data-testid="comment-general-badge">
      general
    </span>
  );
}

export function UnifiedCommentThread({
  projectId,
  feedId,
  sliceId,
  token,
}: UnifiedCommentThreadProps) {
  const [comments, setComments] = useState<UnifiedComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchAll = async (): Promise<UnifiedComment[]> => {
    const feedComments = await listFeedComments(token, projectId, feedId);
    const merged = feedComments.map(fromFeedComment);
    merged.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    return merged;
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMessage(null);

    void fetchAll()
      .then((items) => {
        if (active) setComments(items);
      })
      .catch(() => {
        if (active) setErrorMessage("Unable to load comments.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [feedId, projectId, sliceId, token]);

  const handleSubmit = () => {
    const trimmed = draft.trim();
    if (!trimmed || submitting) return;

    setSubmitting(true);
    setErrorMessage(null);
    void createFeedComment(token, projectId, feedId, trimmed, sliceId)
      .then(() => {
        setDraft("");
        return fetchAll();
      })
      .then((items) => setComments(items))
      .catch(() => setErrorMessage("Unable to add comment."))
      .finally(() => setSubmitting(false));
  };

  return (
    <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-slate-900">Discussion</h2>
        <p className="text-sm text-slate-500">
          All comments on this feed —{" "}
          <span className="text-blue-700 font-medium">general</span> and{" "}
          <span className="text-amber-700 font-medium">slice</span> threads combined.
        </p>
      </div>

      {errorMessage && (
        <div role="alert" className="mb-4 rounded-xl border border-error/40 bg-error/10 px-4 py-3 text-sm text-error">
          {errorMessage}
        </div>
      )}

      <div className="mb-5 space-y-3">
        <textarea
          className="min-h-28 w-full rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-primary"
          placeholder="Add a comment..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="flex justify-end">
          <button
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            disabled={!draft.trim() || submitting}
            onClick={handleSubmit}
            type="button"
          >
            Add comment
          </button>
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-600">
          Loading comments...
        </div>
      ) : comments.length === 0 ? (
        <div className="rounded-xl border border-dashed border-outline-variant bg-surface px-4 py-6 text-sm text-slate-500">
          No comments yet.
        </div>
      ) : (
        <div className="space-y-3">
          {[...comments].reverse().map((comment) => (
            <article key={comment.key} className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-semibold text-slate-900">{comment.displayName ?? comment.userId}</span>
                <RoleBadge role={comment.role} />
                <SourceBadge version={comment.sourceSliceVersion} />
                <span className="text-xs text-slate-500">{formatTimestamp(comment.createdAt)}</span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{comment.body}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
