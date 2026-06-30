Task: tasks/001i-ui-template-foundation.md
Domain: docs/domain/ui.md

## Current State

The Katana repo currently has only the domain bundle and task/plan artifacts.
There is no checked-in UI application tree yet.

The external `mockmigration` repository is available at `/private/tmp/mockmigration`
and contains the reusable presentational sources we want to repurpose:

- `src/components/Topbar.tsx`
- `src/components/Sidebar.tsx`
- `src/components/LoginView.tsx`
- `src/components/Portfolio.tsx`
- `src/components/ProjectDetail.tsx`
- `src/index.css`

Those files are useful as layout and interaction references, but they are
coupled to a demo `AppContext`, seeded data, and a dark slate theme. The Katana
domain docs require the opposite: a light tokenized shell, session-authoritative
role handling, and no fake login or seeded local state.

## Objective

Extract the reusable UI patterns from the mockmigration templates and rehome
them as Katana UI primitives. The deliverable is the first execution slice for
the UI work: a shared shell, a login template, and role-aware topbar/sidebar
components that later UI tasks can compose into the full operator experience.

## Out of Scope

- Do NOT implement API calls for login, password reset, or session refresh.
- Do NOT copy the mockmigration `AppContext` or `data.ts` demo state into Katana.
- Do NOT implement portfolio, project-detail, run, or reconciliation business
  data in this task.
- Do NOT preserve the mockmigration dark theme or its demo credential shortcuts.

## Blast Radius

| File | Action | What changes |
|------|--------|-------------|
| `web/app/layout.tsx` | create | root shell wrapper and font/token hookup |
| `web/app/page.tsx` | create | login-or-shell entry point for the template layer |
| `web/app/globals.css` | create | Katana token set and shared shell utilities |
| `web/components/Topbar.tsx` | create | role-aware topbar template derived from mockmigration |
| `web/components/Sidebar.tsx` | create | role-aware sidebar template derived from mockmigration |
| `web/components/LoginView.tsx` | create | login template without demo accounts or fake auth |
| `web/lib/session.ts` | create | UI session shape and authority accessors |
| `web/lib/ui-model.ts` | create | nav and chrome view-model helpers |
| `web/components/__tests__/Topbar.test.tsx` | create | shell/navigation rendering smoke test |
| `web/components/__tests__/LoginView.test.tsx` | create | login template smoke test |

## File Changes

### `web/app/globals.css`

```css
:root {
  --color-surface: #f8f9fa;
  --color-surface-container: #ffffff;
  --color-surface-dim: #d9dadb;
  --color-outline: #e5e7eb;
  --color-outline-variant: #f3f4f5;
  --color-primary: #4f46e5;
  --color-on-primary: #ffffff;
  --color-primary-container: #eef2ff;
  --color-on-primary-container: #3730a3;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-info: #3b82f6;
  --color-neutral: #6b7280;
  --font-sans: "Inter", system-ui, -apple-system, sans-serif;
  --font-mono: "JetBrains Mono", monospace;
  --spacing-container: 1.5rem;
  --spacing-element: 1rem;
  --row-height-compact: 38px;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
}

body {
  background-color: var(--color-surface);
  color: #1f2937;
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
}

.table-row {
  height: var(--row-height-compact);
  border-bottom: 1px solid var(--color-outline-variant);
}

.status-chip {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 9999px;
}

.mono-id {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-neutral);
}

.text-headline-sm {
  font-size: 18px;
  line-height: 24px;
  font-weight: 600;
}

.text-label-mono {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 16px;
  font-weight: 500;
}

.text-on-surface-variant {
  color: #464555;
}

.bg-surface-container-lowest {
  background-color: var(--color-surface-container);
}

.nav-item-active {
  color: var(--color-primary);
  position: relative;
}

.nav-item-active::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -12px;
  height: 2px;
  background-color: var(--color-primary);
}
```

### `web/lib/session.ts`

```ts
export type SessionRole = "central_team" | "project_stakeholder" | "read_only_auditor";

export interface UiSession {
  userId: string;
  role: SessionRole;
  projectIds: string[];
}

export function getUiSession(): UiSession | null {
  return null;
}
```

### `web/lib/ui-model.ts`

```ts
export interface NavItem {
  label: string;
  href: string;
  active?: boolean;
  badge?: string;
  disabled?: boolean;
}

export function navItemsForRole(role: "central_team" | "project_stakeholder" | "read_only_auditor"): NavItem[] {
  const common: NavItem[] = [
    { label: "Portfolio", href: "/", active: true },
    { label: "Projects", href: "/projects" },
    { label: "Runs", href: "/runs" },
    { label: "Approvals", href: "/approvals" },
    { label: "Reconciliation", href: "/reconciliation" },
  ];

  if (role === "central_team") {
    return [...common, { label: "Admin", href: "/admin" }];
  }

  return common;
}
```

### `web/components/Topbar.tsx`

```tsx
import { navItemsForRole, type NavItem } from "../lib/ui-model";

export interface TopbarProps {
  role: "central_team" | "project_stakeholder" | "read_only_auditor";
  projectLabel: string;
}

export function Topbar({ role, projectLabel }: TopbarProps) {
  const items: NavItem[] = navItemsForRole(role);

  return (
    <header className="sticky top-0 z-50 flex h-12 w-full items-center border-b border-outline-variant bg-surface px-6">
      <div className="mr-8 flex items-center">
        <h1 className="text-headline-sm font-bold tracking-tight text-primary">Katana</h1>
      </div>
      <nav className="flex h-full items-center gap-6">
        {items.map((item) => (
          <a key={item.label} className={item.active ? "nav-item-active" : "text-on-surface-variant"} href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-4">
        <input aria-label="Search" placeholder="Search..." type="text" />
        <span className="text-label-mono">{projectLabel}</span>
        <button type="button">Notifications</button>
        <div className="mono-id">AD</div>
      </div>
    </header>
  );
}
```

### `web/components/Sidebar.tsx`

```tsx
import { navItemsForRole } from "../lib/ui-model";

export interface SidebarProps {
  role: "central_team" | "project_stakeholder" | "read_only_auditor";
  collapsed?: boolean;
}

export function Sidebar({ role, collapsed = false }: SidebarProps) {
  const items = navItemsForRole(role);

  return (
    <aside className={collapsed ? "w-14" : "w-64"}>
      <div>Katana</div>
      <nav>
        {items.map((item) => (
          <a key={item.label} href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>
    </aside>
  );
}
```

### `web/components/LoginView.tsx`

```tsx
export interface LoginViewProps {
  onSubmit: (email: string, password: string) => void;
  onBootstrap: () => void;
}

export function LoginView({ onSubmit, onBootstrap }: LoginViewProps) {
  return (
    <div>
      <h1>Katana Console</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          onSubmit(String(form.get("email") ?? ""), String(form.get("password") ?? ""));
        }}
      >
        <label>
          Email
          <input name="email" type="email" required />
        </label>
        <label>
          Password
          <input name="password" type="password" required />
        </label>
        <button type="submit">Sign In</button>
      </form>
      <button type="button" onClick={onBootstrap}>Bootstrap Admin</button>
    </div>
  );
}
```

### `web/app/layout.tsx`

```tsx
import type { ReactNode } from "react";
import "./globals.css";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html className="light" lang="en">
      <body>{children}</body>
    </html>
  );
}
```

### `web/app/page.tsx`

```tsx
import { LoginView } from "../components/LoginView";
import { Sidebar } from "../components/Sidebar";
import { Topbar } from "../components/Topbar";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col">
      <Topbar role="central_team" projectLabel="Acme Core Migration" />
      <div className="flex">
        <Sidebar role="central_team" />
        <section className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 px-6 py-4">
          <div className="min-h-[600px] rounded-xl border border-outline-variant bg-surface-container-lowest" />
          <LoginView onSubmit={() => {}} onBootstrap={() => {}} />
        </section>
      </div>
    </main>
  );
}
```

## Tests

### `web/components/__tests__/Topbar.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { Topbar } from "../Topbar";

describe("Topbar", () => {
  it("renders the Katana brand and role-aware navigation", () => {
    render(<Topbar role="central_team" projectLabel="Acme Core Migration" />);
    expect(screen.getByText("Katana")).toBeInTheDocument();
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });
});
```

### `web/components/__tests__/LoginView.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { LoginView } from "../LoginView";

describe("LoginView", () => {
  it("renders a credential form without demo account shortcuts", () => {
    render(<LoginView onSubmit={() => undefined} onBootstrap={() => undefined} />);
    expect(screen.getByText("Katana Console")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });
});
```

## Verification

```bash
pnpm lint
pnpm test
pnpm build
```

## Pitfalls

- Do NOT copy the mockmigration `AppContext` or `data.ts` into Katana.
- Do NOT preserve demo credentials, seed users, or `localStorage`-backed fake
  auth flows.
- Do NOT keep the dark slate visual language; the Katana token set wins.
- Do NOT let later UI tasks reintroduce a parallel shell instead of reusing
  these primitives.

## Commit

```bash
feat(ui): repurpose mockmigration templates into Katana UI primitives
```
