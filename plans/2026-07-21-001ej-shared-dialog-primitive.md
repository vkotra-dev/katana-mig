# Plan: 001ej — Shared Dialog Primitive

## Task and Domain links

- Task: `tasks/001ej-shared-dialog-primitive.md`
- Domain: `docs/domain/ui.md` (check whether any of the four dialogs' behavior is documented
  there; if the Escape/click-outside change is user-visible enough to warrant a mention, add a
  line per governance I22 — likely minor, confirm before assuming no update needed)

## Current State

- Four independent implementations, confirmed via direct inspection:
  - `AddSourceDialog.tsx:139-140`: `bg-slate-950/50` backdrop, `max-h-[90vh] max-w-2xl
    ... shadow-2xl` container, explicit "Close" button (`:154`), no click-outside, no Escape, no
    `role="dialog"`.
  - `CreateProjectDialog.tsx:44-50`: `bg-black/35` backdrop, `max-w-xl ... shadow-lg` container,
    explicit close button (`:141`), no click-outside, no Escape, **has** `role="dialog"` +
    `aria-modal="true"` (the only one of the four).
  - `LaunchRunDialog.tsx:328-329`: `bg-slate-950/50` backdrop, `max-h-[92vh] max-w-4xl
    ... shadow-2xl` container, explicit close button (`:340,368`), no click-outside, no Escape, no
    `role="dialog"`.
  - `AiLogViewer.tsx:41-42`: `bg-black/50 backdrop-blur-sm` backdrop **with** `onClick={onClose}`
    (click-outside-to-close), `h-[80vh] max-w-4xl ... shadow-2xl` container with
    `onClick={(e) => e.stopPropagation()}` (needed only to support the click-outside behavior),
    explicit close button (`:49`), no Escape, no `role="dialog"`.
- No `document`-level Escape-to-close precedent anywhere in `web/components` — confirmed via
  grep. The `useEffect` + `addEventListener` + cleanup shape used for click-outside detection in
  `ReviewGrid.tsx:80-89` is the closest precedent to mirror, applied to `keydown`/`Escape`
  instead.
- No existing "shared UI primitives" folder — `web/components/` is organized by domain
  (`projects/`, `runs/`, `feeds/`, `ai-logs/`, `notifications/`, `portfolio/`) plus a handful of
  cross-domain components sitting at the top level (`Sidebar.tsx`, `Topbar.tsx`, `UserForm.tsx`).
  The new `Dialog` belongs at the top level, matching that existing pattern.

## Objective

1. `web/components/Dialog.tsx` (new): canonical backdrop/container/Escape-to-close/ARIA, width
   configurable per use, no click-outside.
2. Migrate all four existing dialogs onto it.
3. Remove `AiLogViewer`'s click-outside handler and its now-unneeded `stopPropagation`.

## Out of Scope

- Dialog *content* (forms, wizard steps, tab content) — untouched.
- Focus trapping — not present today, not added here.
- Open/close animation — not present today, not added here.

## Blast Radius

- `web/components/Dialog.tsx` (new)
- `web/components/__tests__/Dialog.test.tsx` (new)
- `web/components/projects/AddSourceDialog.tsx` (edited)
- `web/components/projects/CreateProjectDialog.tsx` (edited)
- `web/components/runs/LaunchRunDialog.tsx` (edited)
- `web/components/ai-logs/AiLogViewer.tsx` (edited)
- Existing test files for all four dialogs (edited — assertions on backdrop
  classNames/structure will need updating to match the new shared markup)
- No backend change.

## File Changes

**`web/components/Dialog.tsx` (new)**
```tsx
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
```
- No `onClick` anywhere on the backdrop — deliberate, per the decided interaction model.
- `widthClassName` defaults to `max-w-2xl` (a reasonable middle value) but every call site should
  pass its own — don't rely on the default for dialogs whose current width differs.
- `AiLogViewer`'s current structure (`flex h-[80vh] flex-col ... overflow-hidden`, tabs inside)
  differs enough from the simple `overflow-y-auto` others use that it may need to render its own
  inner layout *inside* `Dialog`'s `children` rather than trying to force one generic body
  layout — confirm this while migrating, don't flatten a real structural difference into a
  one-size-fits-all body wrapper.

**Four call sites**
- Each replaces its own backdrop/container markup with `<Dialog open={...} onClose={...}
  widthClassName="...">...</Dialog>`, passing its existing header/body/footer content as
  children, keeping each dialog's existing Close/Cancel button (all four already have one — not
  adding new buttons, just keeping what's there inside the new wrapper).
- `AiLogViewer.tsx`: remove the backdrop's `onClick={onClose}` and the inner container's
  `onClick={(e) => e.stopPropagation()}` — both existed only to implement click-outside, which is
  being removed.

## Tests

- `Dialog.test.tsx`: renders `children` when `open`; renders nothing when `!open`; calls
  `onClose` on Escape keydown; does NOT call `onClose` on a click anywhere (backdrop or
  container) — a regression test for the "no click-outside" decision, since that's the one
  behavior most likely to get silently reintroduced by a future edit; has `role="dialog"` +
  `aria-modal="true"`.
- Existing test files for all four dialogs: update any assertions tied to the old inline
  backdrop/container classNames or structure; add/confirm an Escape-closes assertion per dialog.

## Verification

- Manually open each of the four dialogs in the browser: confirm consistent backdrop appearance,
  Escape closes each, clicking outside does NOT close any of them, the existing Close/Cancel
  button still works, and each dialog's actual content/functionality (form submission, wizard
  step navigation, AI log tab switching) is unaffected.
- Full frontend test suite green.

## Pitfalls

- Don't force `AiLogViewer`'s internal `flex h-[80vh] flex-col` tab layout into `Dialog`'s
  generic `overflow-y-auto` body wrapper if it doesn't fit cleanly — it's fine for that one
  dialog's children to bring their own inner layout structure; `Dialog` owns the
  backdrop/container/close behavior, not necessarily every dialog's internal scrolling model.
- Verify no test elsewhere (e.g. `LaunchRunDialog.test.tsx`) asserts on the exact backdrop
  className string (`bg-slate-950/50` etc.) — those will need updating, not just the dialog
  components themselves.
- Confirm removing `AiLogViewer`'s `stopPropagation` doesn't have a side effect on any other click
  handler inside it that was implicitly relying on event bubbling being stopped there — check
  before deleting, don't assume it was purely for the click-outside mechanism.

## Commit

Own commit. No dependency on any other in-flight task.
