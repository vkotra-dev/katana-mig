"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { canAccessAdmin } from "../../lib/navigation-access";
import { loadUiSession } from "../../lib/session";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    const session = loadUiSession();
    if (!session || !canAccessAdmin(session.role)) {
      router.replace("/");
      return;
    }

    setAllowed(true);
  }, [router]);

  if (!allowed) {
    return null;
  }

  return <>{children}</>;
}
