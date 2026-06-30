"use client";

export type UserRole = "central_team" | "project_stakeholder" | "read_only_auditor";
export type UserStatus = "active" | "disabled";

export interface UserFormValue {
  email: string;
  password?: string;
  displayName: string | null;
  role: UserRole;
  status: UserStatus;
}

export interface UserFormProps {
  mode: "create" | "edit";
  initialValue?: {
    email: string;
    displayName: string | null;
    role: UserRole;
    status: UserStatus;
  };
  loading?: boolean;
  errorMessage?: string;
  onSubmit: (value: UserFormValue) => Promise<void> | void;
}

export function UserForm({
  mode,
  initialValue,
  loading = false,
  errorMessage,
  onSubmit,
}: UserFormProps) {
  const title = mode === "create" ? "Create user" : "Update user";
  const submitLabel = mode === "create" ? "Create user" : "Save changes";

  return (
    <form
      className="space-y-5 rounded-2xl border border-outline-variant bg-surface-container p-8 shadow-sm"
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        void onSubmit({
          email: String(form.get("email") ?? ""),
          password: mode === "create" ? String(form.get("password") ?? "") : undefined,
          displayName: String(form.get("displayName") ?? "") || null,
          role: String(form.get("role") ?? "project_stakeholder") as UserRole,
          status: String(form.get("status") ?? "active") as UserStatus,
        });
      }}
    >
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        <p className="text-sm text-slate-600">
          {mode === "create"
            ? "Create a platform user with the correct role and account status."
            : "Update the profile, role, or status for this platform user."}
        </p>
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Email</label>
        <input
          className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
          defaultValue={initialValue?.email ?? ""}
          name="email"
          placeholder="operator@example.com"
          required
          type="email"
        />
      </div>

      {mode === "create" ? (
        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Password</label>
          <input
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
            name="password"
            placeholder="Initial password"
            required
            type="password"
          />
        </div>
      ) : null}

      <div className="space-y-2">
        <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Display name</label>
        <input
          className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
          defaultValue={initialValue?.displayName ?? ""}
          name="displayName"
          placeholder="Operator"
          type="text"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Role</label>
          <select
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
            defaultValue={initialValue?.role ?? "project_stakeholder"}
            name="role"
          >
            <option value="central_team">central_team</option>
            <option value="project_stakeholder">project_stakeholder</option>
            <option value="read_only_auditor">read_only_auditor</option>
          </select>
        </div>

        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Status</label>
          <select
            className="w-full rounded-md border border-outline-variant bg-white px-3 py-3 text-sm text-slate-900"
            defaultValue={initialValue?.status ?? "active"}
            name="status"
          >
            <option value="active">active</option>
            <option value="disabled">disabled</option>
          </select>
        </div>
      </div>

      {errorMessage ? (
        <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
          {errorMessage}
        </p>
      ) : null}

      <button
        className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
        disabled={loading}
        type="submit"
      >
        {loading ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}
