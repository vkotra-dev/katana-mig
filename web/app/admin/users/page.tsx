"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { UserList, type UserRecord } from "../../../components/UserList";
import { deleteUser, listUsers, type UserResponse } from "../../../lib/management-api";
import { loadUiSession } from "../../../lib/session";

function toUserRecord(user: UserResponse): UserRecord {
  return {
    userId: user.userId,
    email: user.email,
    displayName: user.displayName,
    role: user.role,
    status: user.status,
  };
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | undefined>();
  const session = useMemo(() => loadUiSession(), []);

  useEffect(() => {
    if (!session) {
      return;
    }

    void listUsers(session.accessToken)
      .then(setUsers)
      .catch((error: unknown) => {
        setErrorMessage(error instanceof Error ? error.message : "Unable to load users.");
      });
  }, [session]);

  const handleDelete = async (userId: string) => {
    if (!session) {
      return;
    }

    await deleteUser(session.accessToken, userId);
    const nextUsers = await listUsers(session.accessToken);
    setUsers(nextUsers);
  };

  return (
    <main className="min-h-screen bg-surface px-6 py-8 text-slate-800">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Admin</p>
            <h1 className="text-3xl font-semibold text-slate-900">User management</h1>
          </div>
          <Link className="rounded-md bg-primary px-4 py-3 text-sm font-semibold text-white" href="/admin/users/new">
            Create user
          </Link>
        </div>

        {errorMessage ? (
          <p className="rounded-md border border-error/30 bg-error/10 px-3 py-2 text-sm text-error" role="alert">
            {errorMessage}
          </p>
        ) : null}

        <UserList onDelete={(userId) => void handleDelete(userId)} users={users.map(toUserRecord)} />
      </div>
    </main>
  );
}
