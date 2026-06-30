Task: tasks/001l-ui-auth-api-wiring.md
Domain: docs/domain/auth.md

## Current State

The web app currently has a login card, a top-level page that renders it, and a
placeholder `getUiSession()` helper that always returns `null`. The auth API is
already implemented in the engine and documented in `docs/domain/api.md`, but
the UI does not yet call it.

The current UI code also has no shared API client, no stored session model, and
no password-reset screens beyond the login page link.

## Objective

Replace the local login stub with real auth API wiring so the UI can log in,
restore a session, log out, and drive password-reset flows against the backend.
This task should keep session authority in the backend response and should not
introduce any role claims from request bodies.

## Out of Scope

- User creation and membership administration
- Navigation RBAC beyond selecting the authenticated landing view
- Backend auth implementation changes
- New visual redesign work

## Blast Radius

| File | Action | What changes |
|------|--------|--------------|
| `web/lib/session.ts` | modify | Store and resolve the authenticated UI session |
| `web/lib/auth-api.ts` | create | Fetch wrappers for login, session, logout, and password reset |
| `web/lib/api-base.ts` | create | Shared API base URL and JSON helper |
| `web/app/page.tsx` | modify | Load session and route between login and authenticated shell |
| `web/app/auth/password-reset/page.tsx` | create | Password-reset request screen |
| `web/app/auth/password-reset/confirm/page.tsx` | create | Password-reset confirm screen |
| `web/components/LoginView.tsx` | modify | Submit real credentials and show API errors |
| `web/components/PasswordResetRequestView.tsx` | create | Request form for password reset |
| `web/components/PasswordResetConfirmView.tsx` | create | Confirm form for password reset |
| `web/lib/auth-api.test.ts` | create | Cover endpoint payloads and session mapping |
| `web/components/__tests__/LoginView.test.tsx` | modify | Cover login submission behavior |
| `web/app/__tests__/page.test.tsx` | modify | Cover session restore and login routing |
| `web/app/auth/password-reset/page.test.tsx` | create | Cover password-reset request submission |
| `web/app/auth/password-reset/confirm/page.test.tsx` | create | Cover password-reset confirm submission |

## File Changes

### `web/lib/api-base.ts`

```ts
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function jsonRequest<TResponse>(
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<TResponse> {
  const { token, headers, ...rest } = init;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return (await response.json()) as TResponse;
}
```

### `web/lib/session.ts`

```ts
export interface UiSession {
  accessToken: string;
  expiresAt: string;
  role: SessionRole;
  sessionVersion: number;
  userId: string;
}

export function loadUiSession(): UiSession | null;
export function saveUiSession(session: UiSession): void;
export function clearUiSession(): void;
```

### `web/lib/auth-api.ts`

```ts
export function login(email: string, password: string): Promise<LoginResponse>;
export function fetchSession(token: string): Promise<SessionResponse>;
export function logout(token: string): Promise<void>;
export function requestPasswordReset(email: string): Promise<PasswordResetAccepted>;
export function confirmPasswordReset(resetToken: string, newPassword: string): Promise<void>;
export function getBootstrapStatus(): Promise<BootstrapStatusResponse>;
```

### `web/app/page.tsx`

```tsx
export default function HomePage() {
  // On mount: read stored session, verify it with /auth/session, and render
  // login if the session is absent or invalid.
}
```

### `web/components/LoginView.tsx`

```tsx
export interface LoginViewProps {
  onSubmit: (email: string, password: string) => Promise<void>;
  errorMessage?: string;
  loading?: boolean;
}
```

## Tests

### `web/lib/auth-api.test.ts`

```ts
import { login, fetchSession, logout } from "../lib/auth-api";

describe("auth-api", () => {
  it("posts credentials to /auth/login", async () => {
    // Mock fetch and assert payload, path, and JSON response mapping.
  });
});
```

### `web/components/__tests__/LoginView.test.tsx`

```tsx
it("submits the entered credentials", async () => {
  // Render the form, type into the fields, submit, and assert the callback.
});
```

### `web/app/__tests__/page.test.tsx`

```tsx
it("renders login when no stored session exists", () => {
  // Verify the unauthenticated boot path.
});
```

## Verification

- `npm test` from `web` passes the auth component and API tests
- `npm run build` from `web` still succeeds after the new auth pages are added
- Manual check: login, session restore, logout, and password reset hit the
  documented endpoints

## Pitfalls

- Do not trust caller-supplied role values from forms
- Do not leave the login page on a fake callback after the API client exists
- Keep password-reset request and confirm separate so the endpoint contracts do
  not blur together
- Make sure session invalidation clears persisted state before redirecting

## Commit

- `feat(ui): wire auth flows to the backend API`
