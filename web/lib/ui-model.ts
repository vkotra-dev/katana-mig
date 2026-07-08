import type { SessionRole } from "./session";
import { canAccessAdmin } from "./navigation-access";

export interface NavItem {
  label: string;
  href: string;
  active?: boolean;
  badge?: string;
  children?: NavItem[];
}

export function navItemsForRole(role: SessionRole): NavItem[] {
  const common: NavItem[] = [
    { label: "Portfolio", href: "/", active: true },
    { label: "Projects", href: "/projects" },
    { label: "Runs", href: "/runs" },
    { label: "Reconciliation", href: "/reconciliation" },
  ];

  if (canAccessAdmin(role)) {
    if (role === "admin") {
      return [
        ...common,
        {
          label: "Admin",
          href: "/admin",
          children: [
            { label: "Manage Users", href: "/admin/users" },
            { label: "Assign PM to Project", href: "/admin/assign-pm" },
          ],
        },
      ];
    }
    return [...common, { label: "Admin", href: "/admin" }];
  }

  return common;
}
