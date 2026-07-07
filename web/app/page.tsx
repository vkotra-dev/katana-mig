"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LoginView } from "../components/LoginView";
import { Topbar } from "../components/Topbar";
import {
  fetchSession,
  getBootstrapStatus,
  login,
  type LoginResponse,
  type SessionResponse,
} from "../lib/auth-api";
import { clearUiSession, loadUiSession, saveUiSession, type SessionRole, type UiSession } from "../lib/session";

type AuthStatus = "loading" | "unauthenticated" | "authenticated";

function toUiSession(
  response: LoginResponse,
  accessToken: string,
): UiSession {
  return {
    accessToken,
    expiresAt: response.expiresAt,
    role: response.user.role,
    sessionVersion: response.sessionVersion,
    userId: response.user.user_id,
    projectIds: response.projectIds,
  };
}

function toUiSessionFromCurrentSession(
  response: SessionResponse,
  accessToken: string,
): UiSession {
  return {
    accessToken,
    expiresAt: response.expires_at,
    role: response.role,
    sessionVersion: response.session_version,
    userId: response.user_id,
    projectIds: response.project_ids,
  };
}

function AuthenticatedShell({
  role,
}: {
  role: SessionRole;
}) {
  return (
    <main className="flex min-h-screen flex-col bg-surface text-slate-800">
      <Topbar role={role} />
      <section className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-4 px-6 py-4">
        <div className="min-h-[600px] rounded-xl border border-outline-variant bg-surface-container-lowest" />
      </section>
    </main>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<UiSession | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [bootstrapRequired, setBootstrapRequired] = useState(false);

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  useEffect(() => {
    let active = true;

    const restore = async () => {
      try {
        const bootstrap = await getBootstrapStatus();
        if (active) {
          setBootstrapRequired(bootstrap.bootstrap_required);
        }
      } catch {
        if (active) {
          setBootstrapRequired(false);
        }
      }

      const storedSession = loadUiSession();
      if (!storedSession) {
        if (active) {
          setStatus("unauthenticated");
        }
        return;
      }

      try {
        const currentSession = await fetchSession(storedSession.accessToken);
        const nextSession = toUiSessionFromCurrentSession(currentSession, storedSession.accessToken);
        saveUiSession(nextSession);
        if (active) {
          setSession(nextSession);
          setStatus("authenticated");
        }
      } catch {
        clearUiSession();
        if (active) {
          setSession(null);
          setStatus("unauthenticated");
        }
      }
    };

    void restore();

    return () => {
      active = false;
    };
  }, []);

  const handleLogin = async (email: string, password: string) => {
    setLoading(true);
    setErrorMessage(undefined);

    try {
      const response = await login(email, password);
      const nextSession = toUiSession(response, response.accessToken);
      saveUiSession(nextSession);
      setSession(nextSession);
      setStatus("authenticated");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to sign in.");
    } finally {
      setLoading(false);
    }
  };

  if (status === "authenticated" && session) {
    return <AuthenticatedShell role={session.role} />;
  }

  if (status === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface px-6 py-12 text-slate-800">
        <div className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface-container px-4 py-3 text-sm text-slate-700">
          Restoring your session...
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface px-6 py-12 text-slate-800">
      <div className="w-full max-w-lg space-y-4">
        <LoginView errorMessage={errorMessage} loading={loading} onSubmit={handleLogin} />
        {bootstrapRequired ? (
          <p className="rounded-xl border border-outline-variant bg-surface-container px-4 py-3 text-sm text-slate-700">
            First-run administrator bootstrap is required before normal login can succeed.
          </p>
        ) : null}
      </div>
    </main>
  );
}
