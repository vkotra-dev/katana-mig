import type { SessionRole } from "./session";
import { canAccessAdmin } from "./navigation-access";

export interface NavItem {
  label: string;
  href: string;
  active?: boolean;
  badge?: string;
}

export function navItemsForRole(role: SessionRole): NavItem[] {
  const common: NavItem[] = [
    { label: "Portfolio", href: "/", active: true },
    { label: "Projects", href: "/projects" },
    { label: "Runs", href: "/runs" },
    { label: "Reconciliation", href: "/reconciliation" },
  ];

  if (canAccessAdmin(role)) {
    return [...common, { label: "Admin", href: "/admin" }];
  }

  return common;
}
