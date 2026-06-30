"use client";

import type { UserRole, UserStatus } from "./UserForm";

export interface UserRecord {
  userId: string;
  email: string;
  displayName: string | null;
  role: UserRole;
  status: UserStatus;
}

export interface UserListProps {
  users: UserRecord[];
  onDelete: (userId: string) => void;
  onSelect?: (userId: string) => void;
}

export function UserList({ users, onDelete, onSelect }: UserListProps) {
  return (
    <div className="rounded-2xl border border-outline-variant bg-surface-container shadow-sm">
      <div className="border-b border-outline-variant px-6 py-4">
        <h2 className="text-lg font-semibold text-slate-900">Users</h2>
      </div>
      <ul>
        {users.map((user) => (
          <li key={user.userId} className="flex items-center justify-between border-b border-outline-variant px-6 py-4 last:border-b-0">
            <button className="text-left" onClick={() => onSelect?.(user.userId)} type="button">
              <div className="text-sm font-semibold text-slate-900">{user.email}</div>
              <div className="text-xs text-slate-500">
                {user.displayName ?? "No display name"} · {user.role} · {user.status}
              </div>
            </button>
            <button
              className="rounded-md border border-outline-variant px-3 py-2 text-sm text-slate-700"
              onClick={() => onDelete(user.userId)}
              type="button"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
