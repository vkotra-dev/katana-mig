"use client";

import { useMemo, useState } from "react";
import { UserForm, type UserFormValue } from "../../../../components/UserForm";
import { createUser } from "../../../../lib/management-api";
import { loadUiSession } from "../../../../lib/session";

export default function NewUserPage() {
  const session = useMemo(() => loadUiSession(), []);
  const [successMessage, setSuccessMessage] = useState<string | undefined>();
  const [errorMessage, setErrorMessage] = useState<string | undefined>();

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
        <UserForm errorMessage={errorMessage} mode="create" onSubmit={handleSubmit} />
        {successMessage ? <p className="text-sm text-success">{successMessage}</p> : null}
      </div>
    </main>
  );
}
