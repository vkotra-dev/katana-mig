"use client";

import { navItemsForRole } from "../lib/ui-model";

export interface SidebarProps {
  role: "central_team" | "project_stakeholder" | "read_only_auditor";
  collapsed?: boolean;
}

export function Sidebar({ role, collapsed = false }: SidebarProps) {
  const items = navItemsForRole(role);

  return (
    <aside className={collapsed ? "w-14 shrink-0 border-r border-outline-variant bg-surface-container" : "w-64 shrink-0 border-r border-outline-variant bg-surface-container"}>
      <div className="flex h-12 items-center px-4 text-sm font-semibold text-primary">Katana</div>
      <nav className="flex flex-col gap-1 p-2">
        {items.map((item) => (
          <a key={item.label} className="nav-link" href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>
    </aside>
  );
}
