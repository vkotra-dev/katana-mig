"use client";

import { useEffect, type ReactNode } from "react";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  widthClassName?: string; // e.g. "max-w-xl" | "max-w-2xl" | "max-w-4xl" — caller picks, no default forced
  children: ReactNode;
}

export function Dialog({ open, onClose, title, widthClassName = "max-w-2xl", children }: DialogProps) {
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm px-4 py-8"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className={`max-h-[90vh] w-full ${widthClassName} overflow-y-auto rounded-2xl border border-outline-variant bg-surface-container p-6 shadow-2xl`}>
        {children}
      </div>
    </div>
  );
}
