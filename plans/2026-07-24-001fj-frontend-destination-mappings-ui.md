# Plan: Task 001fj — Ultra-Lightweight React UI Update for Destination 1-to-Many Grid

- **Task**: [001fj-frontend-destination-mappings-ui.md](file:///Users/vjkotra/projects/katana/tasks/001fj-frontend-destination-mappings-ui.md)
- **Domain**: [governance.md](file:///Users/vjkotra/projects/katana/docs/domain/governance.md)

---

## Current State
The UI attempts to invert `source_value_map: dict[str, str]` into groups on the client side, causing clumsy JSX and complex state management.

---

## Objective
Refactor `LookupMappingTable.tsx` and feed/review pages to consume `destination_mappings` directly from the API.

---

## Blast Radius
- `web/lib/lookup-api.ts`
- `web/components/projects/LookupMappingTable.tsx`
- `web/app/projects/[id]/feeds/[feedId]/review/page.tsx`
- `web/app/projects/[id]/feeds/[feedId]/page.tsx`
- `web/components/projects/__tests__/LookupMappingTable.test.tsx`

---

## Detailed Implementation Instructions for Local LLM Agent

### Step 1: Update API Interfaces in `lib/lookup-api.ts`
Add `DestinationMappingGroup` interface:

```typescript
export interface DestinationMappingGroup {
  destId: string;
  destLabel: string;
  destRow?: Record<string, any>;
  sourceValues: string[];
  status: string;
}

export interface LookupValueMapRecord {
  lookupValueMapId: string;
  projectId: string;
  lookupName: string;
  destinationTable: Record<string, any>[];
  sourceValueMap: Record<string, string>;
  destinationMappings: DestinationMappingGroup[];
  status: string;
}
```

### Step 2: Refactor `LookupMappingTable.tsx`
Simplify component to map over `destinationMappings` directly:

```tsx
interface Props {
  groups: DestinationMappingGroup[];
  editingEnabled?: boolean;
  onAddSourceValue?: (destId: string, sourceValue: string) => void;
  onRemoveSourceValue?: (destId: string, sourceValue: string) => void;
}

export function LookupMappingTable({ groups, editingEnabled, onAddSourceValue, onRemoveSourceValue }: Props) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full text-left text-sm text-slate-700">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500 font-semibold border-b border-slate-200">
          <tr>
            <th className="py-3 px-4 w-1/3">Destination Value (ID)</th>
            <th className="py-3 px-4 w-1/2">Mapped Source Values</th>
            <th className="py-3 px-4 w-1/6">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {groups.map((group) => (
            <tr key={group.destId} className="hover:bg-slate-50/50">
              <td className="py-3 px-4 font-medium text-slate-900">
                {group.destLabel}{" "}
                <span className="text-slate-400 font-normal">({group.destId})</span>
              </td>
              <td className="py-3 px-4">
                <div className="flex flex-col gap-1.5 w-full">
                  {group.sourceValues.map((srcVal, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <input
                        type="text"
                        readOnly={!editingEnabled}
                        value={srcVal}
                        className="px-2.5 py-1 text-sm border rounded bg-slate-50 border-slate-200 text-slate-800 focus:outline-none focus:bg-white focus:border-indigo-500 w-full max-w-sm"
                      />
                      {editingEnabled && onRemoveSourceValue && (
                        <button
                          type="button"
                          onClick={() => onRemoveSourceValue(group.destId, srcVal)}
                          className="text-slate-400 hover:text-red-500 p-1 font-bold"
                          title="Remove source value"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                  {editingEnabled && onAddSourceValue && (
                    <button
                      type="button"
                      onClick={() => {
                        const val = prompt("Enter new source value alias:");
                        if (val && val.trim()) {
                          onAddSourceValue(group.destId, val.trim());
                        }
                      }}
                      className="text-xs text-indigo-600 font-medium hover:text-indigo-800 self-start mt-1"
                    >
                      + Add another source value
                    </button>
                  )}
                </div>
              </td>
              <td className="py-3 px-4">
                <StatusBadge status={group.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## Tests
```bash
cd web && npm run test
```

---

## Verification Checklist
- [ ] Component renders 1-to-Many Destination groups directly without client-side inversion.
- [ ] `+ Add another source value` and `×` buttons fire discrete API actions.
- [ ] All 317 vitest frontend tests pass 100%.

---

## Commit
`feat(ui,lookup): simplify LookupMappingTable to consume destination_mappings directly (001fj)`
