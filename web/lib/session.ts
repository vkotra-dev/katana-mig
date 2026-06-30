export type SessionRole = "central_team" | "project_stakeholder" | "read_only_auditor";

export interface UiSession {
  accessToken: string;
  expiresAt: string;
  userId: string;
  role: SessionRole;
  sessionVersion: number;
  projectIds?: string[];
}

const SESSION_STORAGE_KEY = "katana.ui.session";
let memorySession: string | null = null;

function readStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  if (typeof process !== "undefined" && process.env.NODE_ENV === "test") {
    return null;
  }

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function readSessionJson(): string | null {
  const storage = readStorage();
  if (storage) {
    return storage.getItem(SESSION_STORAGE_KEY);
  }

  return memorySession;
}

function writeSessionJson(value: string | null): void {
  const storage = readStorage();
  if (storage) {
    if (value === null) {
      storage.removeItem(SESSION_STORAGE_KEY);
      return;
    }

    storage.setItem(SESSION_STORAGE_KEY, value);
    return;
  }

  memorySession = value;
}

export function loadUiSession(): UiSession | null {
  const raw = readSessionJson();
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as UiSession;
  } catch {
    return null;
  }
}

export function saveUiSession(session: UiSession): void {
  writeSessionJson(JSON.stringify(session));
}

export function clearUiSession(): void {
  writeSessionJson(null);
}

export function getUiSession(): UiSession | null {
  return loadUiSession();
}
