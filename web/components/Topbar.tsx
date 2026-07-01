"use client";

import { useEffect, useState } from "react";
import { navItemsForRole, type NavItem } from "../lib/ui-model";
import { getPendingApprovalCount } from "../lib/feed-slice-approval-api";
import { loadUiSession } from "../lib/session";

export interface TopbarProps {
  role: "central_team" | "project_stakeholder" | "read_only_auditor";
}

export function Topbar({ role }: TopbarProps) {
  const [approvalCount, setApprovalCount] = useState<number | null>(null);
  const items: NavItem[] = navItemsForRole(role).map((item) =>
    item.label === "Approvals" && approvalCount && approvalCount > 0
      ? { ...item, badge: String(approvalCount) }
      : item,
  );

  useEffect(() => {
    const session = loadUiSession();
    if (!session || role === "read_only_auditor") {
      return;
    }

    let active = true;
    void getPendingApprovalCount(session.accessToken)
      .then((count) => {
        if (active) {
          setApprovalCount(count);
        }
      })
      .catch(() => {
        if (active) {
          setApprovalCount(null);
        }
      });

    return () => {
      active = false;
    };
  }, [role]);

  return (
    <header className="sticky top-0 z-50 flex h-12 w-full items-center border-b border-outline-variant bg-surface px-6">
      <div className="mr-8 flex items-center">
        <h1 className="text-headline-sm font-bold tracking-tight text-primary">Katana</h1>
      </div>
      <nav className="flex h-full items-center gap-6">
        {items.map((item) => (
          <a
            key={item.label}
            className={item.active ? "nav-link nav-item-active" : "nav-link"}
            href={item.href}
          >
            <span className="inline-flex items-center gap-2">
              <span>{item.label}</span>
              {item.badge ? (
                <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[11px] font-semibold text-amber-950">
                  {item.badge}
                </span>
              ) : null}
            </span>
          </a>
        ))}
      </nav>
      <div className="ml-auto flex items-center">
        <div className="mono-id">AD</div>
      </div>
    </header>
  );
}
