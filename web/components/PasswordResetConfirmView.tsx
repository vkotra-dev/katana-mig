"use client";

export interface PasswordResetConfirmViewProps {
  loading?: boolean;
  errorMessage?: string;
  successMessage?: string;
  onSubmit: (resetToken: string, newPassword: string) => Promise<void> | void;
}

export function PasswordResetConfirmView({
  loading = false,
  errorMessage,
  successMessage,
  onSubmit,
}: PasswordResetConfirmViewProps) {
  return (
    <div className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface-container p-10 shadow-sm">
      <div className="mb-10 space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Password reset
        </p>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Confirm your new password</h1>
        <p className="max-w-md text-sm leading-6 text-slate-600">
          Paste the reset token from your email and choose a new password for
          your account.
        </p>
      </div>

      <form
        className="space-y-5"
        method="post"
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          void onSubmit(
            String(form.get("resetToken") ?? ""),
            String(form.get("newPassword") ?? ""),
          );
        }}
      >
        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Reset Token
          </label>
          <input
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20"
            name="resetToken"
            placeholder="Opaque reset token"
            required
            type="text"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            New Password
          </label>
          <input
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20"
            name="newPassword"
            placeholder="New password"
            required
            type="password"
          />
        </div>

        {errorMessage ? (
          <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
            {errorMessage}
          </p>
        ) : null}

        {successMessage ? (
          <p className="rounded-md border border-success/30 bg-success/10 px-3 py-2 text-sm text-slate-800" role="status">
            {successMessage}
          </p>
        ) : null}

        <button
          className="w-full rounded-md px-4 py-3.5 text-sm font-semibold leading-5 shadow-sm transition hover:opacity-95 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={loading}
          style={{
            backgroundColor: "var(--color-primary)",
            color: "var(--color-on-primary)"
          }}
          type="submit"
        >
          {loading ? "Resetting..." : "Reset password"}
        </button>
      </form>

      <div className="mt-8 text-center">
        <a className="text-sm font-medium text-primary hover:underline" href="/">
          Back to sign in
        </a>
      </div>
    </div>
  );
}
