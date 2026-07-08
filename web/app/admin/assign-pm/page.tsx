"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { listProjects, assignProjectManager, type ProjectRecord } from "../../../lib/projects-api";
import { listUsers, type UserResponse } from "../../../lib/management-api";
import { loadUiSession, type UiSession } from "../../../lib/session";

export default function AssignPmPage() {
  const router = useRouter();
  const [session, setSession] = useState<UiSession | null>(null);

  // Data states
  const [allProjects, setAllProjects] = useState<ProjectRecord[]>([]);
  const [allPms, setAllPms] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);

  // Autocomplete states: Projects
  const [projectQuery, setProjectQuery] = useState("");
  const [projectOpen, setProjectOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<ProjectRecord | null>(null);
  const projectContainerRef = useRef<HTMLDivElement>(null);

  // Autocomplete states: PMs
  const [pmQuery, setPmQuery] = useState("");
  const [pmOpen, setPmOpen] = useState(false);
  const [selectedPm, setSelectedPm] = useState<UserResponse | null>(null);
  const pmContainerRef = useRef<HTMLDivElement>(null);

  // Submission/notification states
  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const activeSession = loadUiSession();
    if (!activeSession || activeSession.role !== "admin") {
      router.replace("/");
      return;
    }
    setSession(activeSession);

    // Fetch active projects and users
    void Promise.all([
      listProjects(activeSession.accessToken),
      listUsers(activeSession.accessToken),
    ])
      .then(([projects, users]) => {
        setAllProjects(projects.filter((p) => p.status === "active"));
        setAllPms(users.filter((u) => u.role === "pm" && u.status === "active"));
      })
      .catch((err) => {
        setErrorMessage("Failed to load projects or users data.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [router]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (projectContainerRef.current && !projectContainerRef.current.contains(event.target as Node)) {
        setProjectOpen(false);
      }
      if (pmContainerRef.current && !pmContainerRef.current.contains(event.target as Node)) {
        setPmOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredProjects = allProjects.filter((p) =>
    p.name.toLowerCase().includes(projectQuery.toLowerCase())
  );

  const filteredPms = allPms.filter((pm) => {
    const q = pmQuery.toLowerCase();
    return (
      pm.email.toLowerCase().includes(q) ||
      (pm.displayName ?? "").toLowerCase().includes(q)
    );
  });

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !selectedProject || !selectedPm) return;

    setSubmitting(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      await assignProjectManager(session.accessToken, selectedProject.projectId, selectedPm.userId);
      setSuccessMessage(
        `Successfully assigned Project Manager "${selectedPm.displayName ?? selectedPm.email}" to project "${selectedProject.name}".`
      );
      setSelectedProject(null);
      setProjectQuery("");
      setSelectedPm(null);
      setPmQuery("");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to assign project manager.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-surface px-6 py-8 text-slate-800">
        <div className="mx-auto max-w-xl text-center text-sm text-slate-600">
          Loading active projects and Project Managers...
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-surface px-6 py-8 text-slate-800">
      <div className="mx-auto max-w-xl space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Assign Project Manager</h1>
          <p className="text-sm text-slate-600">
            Select an active project and assign an active Project Manager.
          </p>
        </div>

        {successMessage && (
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-50/80 p-4 text-sm text-emerald-800" role="alert">
            {successMessage}
          </div>
        )}

        {errorMessage && (
          <div className="rounded-xl border border-rose-500/20 bg-rose-50/80 p-4 text-sm text-rose-800" role="alert">
            {errorMessage}
          </div>
        )}

        <form onSubmit={handleAssign} className="rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-sm space-y-5">
          {/* Project Picker */}
          <div ref={projectContainerRef} className="relative space-y-2">
            <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Active Project
            </label>
            <input
              type="text"
              placeholder="Search active projects by name..."
              value={projectQuery}
              onFocus={() => {
                setProjectOpen(true);
                setSuccessMessage(null);
                setErrorMessage(null);
              }}
              onChange={(e) => {
                setProjectQuery(e.target.value);
                setSelectedProject(null);
                setProjectOpen(true);
              }}
              className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-slate-400"
            />
            {projectOpen && filteredProjects.length > 0 && (
              <ul className="absolute left-0 right-0 z-50 mt-1 max-h-60 overflow-auto rounded-md border border-outline-variant bg-white py-1 shadow-lg">
                {filteredProjects.map((p) => (
                  <li
                    key={p.projectId}
                    onClick={() => {
                      setSelectedProject(p);
                      setProjectQuery(p.name);
                      setProjectOpen(false);
                    }}
                    className="cursor-pointer px-4 py-2.5 text-sm text-slate-900 hover:bg-slate-50 transition"
                  >
                    {p.name}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* PM Picker */}
          <div ref={pmContainerRef} className="relative space-y-2">
            <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Active Project Manager
            </label>
            <input
              type="text"
              placeholder="Search Project Managers by email or name..."
              value={pmQuery}
              onFocus={() => {
                setPmOpen(true);
                setSuccessMessage(null);
                setErrorMessage(null);
              }}
              onChange={(e) => {
                setPmQuery(e.target.value);
                setSelectedPm(null);
                setPmOpen(true);
              }}
              className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-slate-400"
            />
            {pmOpen && filteredPms.length > 0 && (
              <ul className="absolute left-0 right-0 z-50 mt-1 max-h-60 overflow-auto rounded-md border border-outline-variant bg-white py-1 shadow-lg">
                {filteredPms.map((pm) => {
                  const label = `${pm.email} — ${pm.displayName ?? "No display name"}`;
                  return (
                    <li
                      key={pm.userId}
                      onClick={() => {
                        setSelectedPm(pm);
                        setPmQuery(label);
                        setPmOpen(false);
                      }}
                      className="cursor-pointer px-4 py-2.5 text-sm text-slate-900 hover:bg-slate-50 transition"
                    >
                      {label}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={!selectedProject || !selectedPm || submitting}
            className="w-full rounded-md bg-primary py-3 text-sm font-semibold text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary/95 transition shadow-sm"
          >
            {submitting ? "Assigning..." : "Assign Project Manager"}
          </button>
        </form>
      </div>
    </main>
  );
}
