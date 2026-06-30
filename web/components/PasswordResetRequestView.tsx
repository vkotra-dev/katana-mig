"use client";

export interface PasswordResetRequestViewProps {
  loading?: boolean;
  errorMessage?: string;
  successMessage?: string;
  onSubmit: (email: string) => Promise<void> | void;
}

export function PasswordResetRequestView({
  loading = false,
  errorMessage,
  successMessage,
  onSubmit,
}: PasswordResetRequestViewProps) {
  return (
    <div className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface-container p-10 shadow-sm">
      <div className="mb-10 space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Password reset
        </p>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Request a reset link</h1>
        <p className="max-w-md text-sm leading-6 text-slate-600">
          Enter your operator email address and we will send a password reset
          request if the account is eligible.
        </p>
      </div>

      <form
        className="space-y-5"
        method="post"
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          void onSubmit(String(form.get("email") ?? ""));
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
          {loading ? "Sending..." : "Send reset link"}
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
