"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Topbar } from "../../components/Topbar";
import { ApprovalsInbox } from "../../components/approvals/ApprovalsInbox";
import { loadUiSession, type SessionRole, type UiSession } from "../../lib/session";

export default function ApprovalsPage() {
  const router = useRouter();
  const [session, setSession] = useState<UiSession | null>(null);

  useEffect(() => {
    const current = loadUiSession();
    if (!current || current.role === "read_only_auditor") {
      router.replace("/");
      return;
    }
    setSession(current);
  }, [router]);

  const role: SessionRole = session?.role ?? "read_only_auditor";

  if (!session) {
    return null;
  }

  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-6">
        <ApprovalsInbox role={role} token={session.accessToken} />
      </section>
    </main>
  );
}
