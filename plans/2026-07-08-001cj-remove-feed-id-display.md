# Plan: 001cj — Remove Feed GUID ID from Project Source List

- **Task Link:** [tasks/001cj-remove-feed-id-display.md](../tasks/001cj-remove-feed-id-display.md)
- **Domain:** [docs/domain/ui.md](../docs/domain/ui.md)

## Current State

In [web/components/projects/SourceList.tsx](file:///Users/vjkotra/projects/katana/web/components/projects/SourceList.tsx):
```tsx
                    <div className="text-sm font-semibold text-slate-900">{source.label}</div>
                    <div className="mono-id mt-1">{source.sourceDefinitionId}</div>
```

This displays the internal GUID under the feed label.

## Objective

Remove the `mono-id` element displaying `source.sourceDefinitionId` from the table row template.

## File Changes

### Step 1 — Update `web/components/projects/SourceList.tsx`

Remove L107:
```tsx
                    <div className="mono-id mt-1">{source.sourceDefinitionId}</div>
```

## Verification

1. Verify TypeScript compiles without errors.
2. Run Vitest tests (`npx vitest run`).

## Commit

```
feat: remove feed/source UUID/GUID display from project source list
```
