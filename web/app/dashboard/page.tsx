"use client";

import { Topbar } from "../../components/Topbar";

export default function DashboardPage() {
  const role = "central_team" as const;

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-4">
        <div className="min-h-[600px] rounded-xl border border-outline-variant bg-surface-container-lowest" />
      </section>
    </main>
  );
}
