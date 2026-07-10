"use client";

import { useState, useEffect, useRef } from "react";
import { logout } from "../lib/auth-api";
import { navItemsForRole, type NavItem } from "../lib/ui-model";
import { clearUiSession, loadUiSession, type SessionRole } from "../lib/session";
import { NotificationBell } from "./notifications/NotificationBell";

export interface TopbarProps {
  role: SessionRole;
}

export function Topbar({ role }: TopbarProps) {
  const items: NavItem[] = navItemsForRole(role);
  const [dropdownOpen, setDropdownOpen] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [initials, setInitials] = useState<string>("AD");

  useEffect(() => {
    const session = loadUiSession();
    if (session) {
      if (session.displayName) {
        const parts = session.displayName.trim().split(/\s+/);
        if (parts.length >= 2) {
          setInitials((parts[0][0] + parts[parts.length - 1][0]).toUpperCase());
        } else if (parts.length === 1 && parts[0]) {
          setInitials(parts[0].slice(0, 2).toUpperCase());
        }
      } else if (session.email) {
        const parts = session.email.split("@")[0].split(/[\._-]/);
        if (parts.length >= 2) {
          setInitials((parts[0][0] + parts[parts.length - 1][0]).toUpperCase());
        } else if (parts.length === 1 && parts[0]) {
          setInitials(parts[0].slice(0, 2).toUpperCase());
        }
      } else {
        const parts = session.role.split(/[-_]/);
        if (parts.length >= 2) {
          setInitials((parts[0][0] + parts[1][0]).toUpperCase());
        } else {
          setInitials(session.role.slice(0, 2).toUpperCase());
        }
      }
    }
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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
        {items.map((item) => {
          if (item.children && item.children.length > 0) {
            const isOpen = dropdownOpen === item.label;
            return (
              <div key={item.label} className="relative" ref={dropdownRef}>
                <button
                  className="nav-link inline-flex items-center gap-1.5 focus:outline-none"
                  onClick={() => setDropdownOpen(isOpen ? null : item.label)}
                  type="button"
                >
                  <span>{item.label}</span>
                  <span className="text-[10px] text-slate-500">▼</span>
                </button>
                {isOpen && (
                  <div className="absolute left-0 mt-1.5 min-w-[200px] z-50 rounded-lg border border-outline-variant bg-white py-1 shadow-lg">
                    {item.children.map((child) => (
                      <a
                        key={child.label}
                        className="block px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition"
                        href={child.href}
                      >
                        {child.label}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            );
          }

          return (
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
          );
        })}
      </nav>
      <div className="ml-auto flex items-center">
        <NotificationBell />
        <div className="mono-id" data-testid="user-initials">{initials}</div>
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
