"use client";

import { logout } from "../lib/auth-api";
import { navItemsForRole, type NavItem } from "../lib/ui-model";
import { clearUiSession, loadUiSession } from "../lib/session";
import { NotificationBell } from "./notifications/NotificationBell";

export interface TopbarProps {
  role: "central_team" | "project_stakeholder" | "read_only_auditor";
}

export function Topbar({ role }: TopbarProps) {
  const items: NavItem[] = navItemsForRole(role);

  const handleLogout = async () => {
    const session = loadUiSession();
    try {
      if (session) {
        await logout(session.accessToken);
      }
    } finally {
      clearUiSession();
      window.location.assign("/");
    }
  };

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
        <NotificationBell />
        <div className="mono-id">AD</div>
        <button
          aria-label="Log out"
          className="ml-4 inline-flex h-9 w-9 items-center justify-center rounded-md border border-outline-variant text-slate-700 hover:bg-outline-variant"
          onClick={() => {
            void handleLogout();
          }}
          title="Log out"
          type="button"
        >
          <svg aria-hidden="true" fill="none" viewBox="0 0 24 24" className="h-4 w-4 stroke-current stroke-2">
            <path d="M15 17l5-5-5-5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M20 12H9" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M13 7V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h5a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </header>
  );
}
