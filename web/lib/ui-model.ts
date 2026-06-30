export interface NavItem {
  label: string;
  href: string;
  active?: boolean;
  badge?: string;
}

export function navItemsForRole(role: "central_team" | "project_stakeholder" | "read_only_auditor"): NavItem[] {
  const common: NavItem[] = [
    { label: "Portfolio", href: "/", active: true },
    { label: "Projects", href: "/projects" },
    { label: "Runs", href: "/runs" },
    { label: "Reconciliation", href: "/reconciliation" },
  ];

  if (role === "central_team") {
    return [...common, { label: "Approvals", href: "/approvals" }, { label: "Admin", href: "/admin" }];
  }

  if (role === "project_stakeholder") {
    return [...common, { label: "Approvals", href: "/approvals" }];
  }

  return common;
}
