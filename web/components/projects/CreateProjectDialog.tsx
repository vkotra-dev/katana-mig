"use client";

import { useEffect, useState } from "react";
import { createProject, projectErrorMessage, type ProjectRecord, type TargetDbEngine } from "../../lib/projects-api";

export interface CreateProjectDialogProps {
  open?: boolean;
  token: string;
  onCreated: (project: ProjectRecord) => void;
  onClose: () => void;
}

export function CreateProjectDialog({
  open,
  token,
  onCreated,
  onClose,
}: CreateProjectDialogProps) {
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [targetDbEngine, setTargetDbEngine] = useState<TargetDbEngine | "">("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    setName("");
    setGoal("");
    setTargetDbEngine("");
    setLoading(false);
    setErrorMessage(null);
  }, [open]);

  if (!open) {
    return null;
  }

  const canSubmit = name.trim().length > 0 && targetDbEngine !== "" && !loading;

  return (
    <div
      aria-label="Create Project"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4 py-8"
      role="dialog"
    >
      <div className="w-full max-w-xl rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-lg">
        <div className="mb-5">
          <h2 className="text-2xl font-semibold text-slate-900">Create project</h2>
          <p className="text-sm text-slate-600">
            Start a new migration project with the project identity and destination contract.
          </p>
        </div>

        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!canSubmit) {
              return;
            }

            setLoading(true);
            setErrorMessage(null);

            try {
              const project = await createProject(token, {
                name: name.trim(),
                goal: goal.trim() || null,
                domainConfig: {
                  targetDbEngine,
                  dryRun: false,
                },
              });
              onCreated(project);
              onClose();
            } catch (error) {
              setErrorMessage(projectErrorMessage(error));
            } finally {
              setLoading(false);
            }
          }}
        >
          <label className="block space-y-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Project name
            </span>
            <input
              aria-label="Project name"
              className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20"
              onChange={(event) => setName(event.target.value)}
              placeholder="CRM migration"
              value={name}
            />
          </label>

          <label className="block space-y-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Goal
            </span>
            <textarea
              aria-label="Goal"
              className="min-h-24 w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20"
              onChange={(event) => setGoal(event.target.value)}
              placeholder="Describe the migration objective"
              value={goal}
            />
          </label>

          <label className="block space-y-2">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Target database engine
            </span>
            <select
              aria-label="Target database engine"
              className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              onChange={(event) => setTargetDbEngine(event.target.value as TargetDbEngine | "")}
              value={targetDbEngine}
            >
              <option value="">Select an engine</option>
              <option value="mssql">mssql</option>
              <option value="oracle">oracle</option>
              <option value="postgresql">postgresql</option>
              <option value="mysql">mysql</option>
            </select>
          </label>

          {errorMessage ? (
            <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
              {errorMessage}
            </p>
          ) : null}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              className="rounded-md border border-outline-variant px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-outline-variant"
              onClick={onClose}
              type="button"
            >
              Cancel
            </button>
            <button
              className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!canSubmit}
              type="submit"
            >
              {loading ? "Creating..." : "Create project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
