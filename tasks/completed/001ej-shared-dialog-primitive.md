---
type: Task Plan
title: Shared Dialog Primitive — Reconcile AddSourceDialog, CreateProjectDialog, LaunchRunDialog, AiLogViewer
status: ready
---

# Task: 001ej-shared-dialog-primitive

## Context
Four dialogs each hand-roll their own backdrop/container: `AddSourceDialog`, `CreateProjectDialog`,
`LaunchRunDialog`, and `AiLogViewer` (built this session). Confirmed via direct code inspection —
not assumed — they diverge on backdrop color, container shadow, and interaction behavior:

| | AddSourceDialog | CreateProjectDialog | LaunchRunDialog | AiLogViewer |
|---|---|---|---|---|
| Backdrop | `bg-slate-950/50` | `bg-black/35` | `bg-slate-950/50` | `bg-black/50` + blur |
| Container shadow | `shadow-2xl` | `shadow-lg` | `shadow-2xl` | `shadow-2xl` |
| Click-outside-to-close | No | No | No | Yes |
| Escape-to-close | No | No | No | No |
| `role="dialog"`/`aria-modal` | No | Yes | No | No |
| Explicit Close/Cancel button | Yes | Yes | Yes | Yes |

All four already have an explicit Close/Cancel button — that part doesn't need adding.

## Decided interaction model (brainstormed, not assumed)
- **Escape closes all four.** Deliberate keypress, low accidental-trigger risk. No existing
  document-level Escape-to-close precedent in this codebase (the two `case "Escape":` handlers in
  `ProjectMembersPanel.tsx:90`/`ReviewGrid.tsx:112` are `onKeyDown` on an autocomplete's input
  element, a different mechanism — a modal's Escape needs to fire regardless of which element
  inside it has focus). What *is* precedented and worth mirroring: the `useEffect` +
  `document.addEventListener` + cleanup-on-unmount shape already used for click-outside detection
  in `ReviewGrid.tsx:80-89`, `ProjectMembersPanel.tsx:61`, `Topbar.tsx:53` — same shape, listening
  for `keydown`/`Escape` instead of `mousedown`/outside-click.
- **Click-outside closes none of them.** Reversed from an earlier draft of this decision — click-
  outside is usually accidental (a stray mouse movement), and 3 of the 4 dialogs already don't
  have it; making `AiLogViewer` consistent with the majority (remove its click-outside) is less
  disruptive than adding it everywhere. Every dialog already has an explicit button as the one,
  unambiguous way to close.
- **This was checked against real consequences, not assumed to be low-risk by default**:
  `AddSourceDialog` genuinely persists a real backend record (`createFeedContract`) before its
  final step — but `SourceList.tsx` renders any such record as a normal, resumable row (no
  "broken" state, an "Open feed" button lets the user finish later), so an accidental early close
  is a minor recoverable annoyance, not data loss — doesn't justify special-casing this one
  dialog differently from the other three.

## Requirements

1. **New shared component** wrapping: backdrop (canonical `bg-black/50 backdrop-blur-sm`,
   matching `AiLogViewer`'s existing look — the most recently-established and most visually
   distinct of the four), container (`rounded-2xl border border-outline-variant
   bg-surface-container shadow-2xl`, canonicalizing on `shadow-2xl` since 3 of 4 already use it),
   `role="dialog"` + `aria-modal="true"` (currently only `CreateProjectDialog` has this — becomes
   standard for all four), and the Escape-to-close `keydown` listener.
2. **Configurable width** — not forced to one size. Each dialog keeps a width suited to its
   content (`CreateProjectDialog` single form ≈ `max-w-xl`, `AddSourceDialog` ≈ `max-w-2xl`,
   `LaunchRunDialog`/`AiLogViewer` wizard/viewer ≈ `max-w-4xl`) via a prop, not a hardcoded value.
3. **No click-outside-to-close** — the backdrop has no `onClick` handler. Remove `AiLogViewer`'s
   existing one (`AiLogViewer.tsx:41`) and its now-unnecessary `onClick={(e) =>
   e.stopPropagation()}` on the inner container (`AiLogViewer.tsx:42`), which existed only to
   support the click-outside behavior being removed.
4. **Migrate all four call sites** onto the new component — this task isn't done until the
   inconsistency is actually gone, not just available for future use.
5. **No behavior change beyond the interaction model above** — same content, same forms, same
   submit logic in all four; only the chrome (backdrop/container/close behavior) changes.

## Out of Scope
- Any change to what's *inside* each dialog (form fields, wizard steps, AI log tab content).
- Focus trapping (tabbing outside the dialog while open) — not currently requested, not present
  in any of the four today; a reasonable future addition but not blocking this task.
- Animation/transition on open/close — none of the four currently have this, not adding it here.

## Dependencies
None.
