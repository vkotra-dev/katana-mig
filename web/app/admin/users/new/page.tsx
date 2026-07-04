"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { UserForm, type UserFormValue } from "../../../../components/UserForm";
import { createUser } from "../../../../lib/management-api";
import { loadUiSession, type UiSession } from "../../../../lib/session";

export default function NewUserPage() {
  const [session, setSession] = useState<UiSession | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | undefined>();
  const [errorMessage, setErrorMessage] = useState<string | undefined>();

  useEffect(() => {
    setSession(loadUiSession());
  }, []);

  const handleSubmit = async (value: UserFormValue) => {
    if (!session || !value.password) {
      return;
    }

    setErrorMessage(undefined);
    setSuccessMessage(undefined);

    try {
      await createUser(session.accessToken, {
        email: value.email,
        password: value.password,
        displayName: value.displayName,
        role: value.role,
      });
      setSuccessMessage("User created successfully.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to create user.");
    }
  };

  return (
    <main className="min-h-screen bg-surface px-6 py-8 text-slate-800">
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Admin</p>
            <h1 className="text-3xl font-semibold text-slate-900">New user</h1>
            <p className="mt-2 text-sm text-slate-600">Create a platform account and assign the right role up front.</p>
          </div>
          <Link className="rounded-md border border-outline-variant px-4 py-3 text-sm font-semibold text-slate-700" href="/admin/users">
            Back to users
          </Link>
        </div>

        <UserForm errorMessage={errorMessage} mode="create" onSubmit={handleSubmit} />
        {successMessage ? <p className="text-sm text-success">{successMessage}</p> : null}
      </div>
    </main>
  );
}
