"use client";

import { useEffect, useState } from "react";
import {
  createFeedComment,
  listFeedComments,
  type FeedCommentRecord,
} from "../../lib/feeds-api";

export interface FeedCommentThreadProps {
  feedId: string;
  projectId: string;
  token: string;
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

export function FeedCommentThread({ feedId, projectId, token }: FeedCommentThreadProps) {
  const [comments, setComments] = useState<FeedCommentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setErrorMessage(null);

    void listFeedComments(token, projectId, feedId)
      .then((items) => {
        if (active) {
          setComments(items);
        }
      })
      .catch(() => {
        if (active) {
          setErrorMessage("Unable to load comments.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [feedId, projectId, token]);

  const handleSubmit = () => {
    const trimmed = draft.trim();
    if (!trimmed || submitting) {
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    void createFeedComment(token, projectId, feedId, trimmed)
      .then(() => {
        setDraft("");
        return listFeedComments(token, projectId, feedId);
      })
      .then((items) => {
        setComments(items);
      })
      .catch(() => {
        setErrorMessage("Unable to add comment.");
      })
      .finally(() => {
        setSubmitting(false);
      });
  };

  return (
    <section className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-slate-900">Comments</h2>
        <p className="text-sm text-slate-500">Feed discussion visible to project collaborators.</p>
      </div>

      {errorMessage ? (
        <div role="alert" className="mb-4 rounded-xl border border-error/40 bg-error/10 px-4 py-3 text-sm text-error">
          {errorMessage}
        </div>
      ) : null}

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
          {comments.map((comment) => (
            <article key={comment.commentId} className="rounded-xl border border-outline-variant bg-surface px-4 py-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-semibold text-slate-900">{comment.displayName ?? comment.userId}</span>
                <RoleBadge role={comment.role} />
                <span className="text-xs text-slate-500">{formatTimestamp(comment.createdAt)}</span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{comment.body}</p>
            </article>
          ))}
        </div>
      )}

      <div className="mt-5 space-y-3">
        <textarea
          className="min-h-28 w-full rounded-xl border border-outline-variant bg-surface px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-primary"
          placeholder="Add a comment..."
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
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
    </section>
  );
}
