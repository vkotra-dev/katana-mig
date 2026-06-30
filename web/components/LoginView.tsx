"use client";

export interface LoginViewProps {
  onSubmit: (email: string, password: string) => Promise<void> | void;
  errorMessage?: string;
  loading?: boolean;
}

export function LoginView({ onSubmit, errorMessage, loading = false }: LoginViewProps) {
  return (
    <div className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface-container p-10 shadow-sm">
      <div className="mb-10 space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Secure access
        </p>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Katana Console</h1>
        <p className="max-w-md text-sm leading-6 text-slate-600">
          Sign in with your operator credentials to continue to the governed migration workspace.
        </p>
      </div>

      <form
        className="space-y-5"
        method="post"
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          onSubmit(String(form.get("email") ?? ""), String(form.get("password") ?? ""));
        }}
      >
        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Operator Email Address
          </label>
          <input
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20"
            name="email"
            placeholder="operator@katana.io"
            type="email"
            required
          />
        </div>

        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Password
          </label>
          <input
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20"
            name="password"
            placeholder="••••••••••••"
            type="password"
            required
          />
        </div>

        {errorMessage ? (
          <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
            {errorMessage}
          </p>
        ) : null}

        <button
          className="w-full rounded-md px-4 py-3.5 text-sm font-semibold leading-5 shadow-sm transition hover:opacity-95 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          style={{
            backgroundColor: "var(--color-primary)",
            color: "var(--color-on-primary)"
          }}
          disabled={loading}
          type="submit"
        >
          {loading ? "Logging in..." : "Log in"}
        </button>
      </form>

      <div className="mt-8 text-center">
        <a className="text-sm font-medium text-primary hover:underline" href="/auth/password-reset">
          Forgot password?
        </a>
      </div>
    </div>
  );
}
