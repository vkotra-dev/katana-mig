"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { canAccessProject } from "../../lib/navigation-access";
import { loadUiSession } from "../../lib/session";

function projectIdFromPathname(pathname: string): string | null {
  const segments = pathname.split("/").filter(Boolean);
  const projectsIndex = segments.indexOf("projects");
  if (projectsIndex === -1) {
    return null;
  }

  return segments[projectsIndex + 1] ?? null;
}

export default function ProjectsLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    const session = loadUiSession();
    if (!session) {
      router.replace("/");
      return;
    }

    const projectId = projectIdFromPathname(pathname);
    if (projectId && !canAccessProject(session.role, projectId, session.projectIds ?? [])) {
      router.replace("/");
      return;
    }

    setAllowed(true);
  }, [pathname, router]);

  if (!allowed) {
    return null;
  }

  return <>{children}</>;
}
