"use client";

import { useEffect, useMemo, useState } from "react";
import { UserForm, type UserFormValue } from "../../../../components/UserForm";
import { getUser, updateUser, type UserResponse } from "../../../../lib/management-api";
import { loadUiSession } from "../../../../lib/session";

export default function UserDetailPage({ params }: any) {
  const session = useMemo(() => loadUiSession(), []);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | undefined>();
  const [errorMessage, setErrorMessage] = useState<string | undefined>();

  useEffect(() => {
    if (!session) {
      return;
    }

    void getUser(session.accessToken, params.userId)
      .then(setUser)
      .catch((error: unknown) => {
        setErrorMessage(error instanceof Error ? error.message : "Unable to load user.");
      });
  }, [params.userId, session]);

  const handleSubmit = async (value: UserFormValue) => {
    if (!session) {
      return;
    }

    setErrorMessage(undefined);
    setSuccessMessage(undefined);

    try {
      const next = await updateUser(session.accessToken, params.userId, {
        displayName: value.displayName,
        role: value.role,
        status: value.status,
      });
      setUser(next);
      setSuccessMessage("User updated successfully.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to update user.");
    }
  };

  return (
    <main className="min-h-screen bg-surface px-6 py-8 text-slate-800">
      <div className="mx-auto max-w-3xl space-y-6">
        {user ? (
          <UserForm
            errorMessage={errorMessage}
            initialValue={{
              email: user.email,
              displayName: user.displayName,
              role: user.role,
              status: user.status,
            }}
            mode="edit"
            onSubmit={handleSubmit}
          />
        ) : (
          <div className="rounded-2xl border border-outline-variant bg-surface-container p-8 text-sm text-slate-600">
            Loading user...
          </div>
        )}
        {successMessage ? <p className="text-sm text-success">{successMessage}</p> : null}
      </div>
    </main>
  );
}
