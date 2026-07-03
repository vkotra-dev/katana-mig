"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { canAccessAdmin } from "../../lib/navigation-access";
import { loadUiSession } from "../../lib/session";
import { Topbar } from "../../components/Topbar";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);
  const [role, setRole] = useState<"central_team" | "project_stakeholder" | "read_only_auditor" | null>(null);

  useEffect(() => {
    const session = loadUiSession();
    if (!session || !canAccessAdmin(session.role)) {
      setRole(null);
      router.replace("/");
      return;
    }

    setRole(session.role);
    setAllowed(true);
  }, [router]);

  if (!allowed) {
    return null;
  }

  return (
    <>
      <Topbar role={role ?? "central_team"} />
      {children}
    </>
  );
}
