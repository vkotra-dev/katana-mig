# Plan: 001eo — Fix AutocompleteInput to Show All Destination Fields When Opened

## Task and Domain links

- Task: `tasks/001eo-autocomplete-lov-show-all-on-open.md`
- Domain: no `docs/domain/` page documents this component's filtering behavior in enough detail
  to need an update.

## Audience note

Written for an agent with no prior context. Every edit gives the exact current text to find and
the exact replacement. Re-read `web/components/projects/ReviewGrid.tsx` lines 58-191 immediately
before starting to confirm it still matches what's quoted below — if it doesn't, stop and report
the discrepancy rather than guessing.

## Current State (verbatim)

`web/components/projects/ReviewGrid.tsx`, lines 58-116 (the parts of `AutocompleteInput` this task
touches — the rest of the component, lines 117-191, is unchanged and not quoted):

```tsx
function AutocompleteInput({
  value,
  options,
  onChange,
  className = "",
  placeholder = "",
}: AutocompleteInputProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  const filteredOptions = query.trim() === ""
    ? options
    : options.filter((opt) =>
        opt.toLowerCase().includes(query.toLowerCase())
      );

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setIsOpen(true);
      setHighlightedIndex((prev) =>
        prev < filteredOptions.length - 1 ? prev + 1 : 0
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIsOpen(true);
      setHighlightedIndex((prev) =>
        prev > 0 ? prev - 1 : filteredOptions.length - 1
      );
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (isOpen && highlightedIndex >= 0 && highlightedIndex < filteredOptions.length) {
        selectOption(filteredOptions[highlightedIndex]);
      } else {
        onChange(query);
        setIsOpen(false);
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  const selectOption = (opt: string) => {
    setQuery(opt);
    onChange(opt);
    setIsOpen(false);
    setHighlightedIndex(-1);
  };
```

Lines 128-144 (the `<input>` element, further down in the same component):

```tsx
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
            setHighlightedIndex(-1);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => {
            onChange(query);
            setIsOpen(false);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={`${className} pr-8`}
        />
```

## Objective

Show all `options` the moment the dropdown opens, before the user has typed anything, while
preserving substring-filtering once they do type, and preserving all existing select/blur/keyboard
behavior exactly.

## File Changes

### `web/components/projects/ReviewGrid.tsx`

**1.** Find this exact block:

```tsx
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  const filteredOptions = query.trim() === ""
    ? options
    : options.filter((opt) =>
        opt.toLowerCase().includes(query.toLowerCase())
      );
```

Replace with (adds a `hasTyped` flag, reset to `false` whenever the underlying `value` prop
changes — i.e. every time a fresh selection has just been made or the picker is showing a new
binding — and set to `true` only by the input's own `onChange` handler in step 2 below):

```tsx
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [hasTyped, setHasTyped] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(value);
    setHasTyped(false);
  }, [value]);

  const filteredOptions = !hasTyped || query.trim() === ""
    ? options
    : options.filter((opt) =>
        opt.toLowerCase().includes(query.toLowerCase())
      );
```

**2.** Find this exact block (the `<input>` element):

```tsx
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
            setHighlightedIndex(-1);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => {
            onChange(query);
            setIsOpen(false);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={`${className} pr-8`}
        />
```

Replace with (only the `onChange` handler gains one new line, `setHasTyped(true)`; everything else
in this block is unchanged):

```tsx
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setHasTyped(true);
            setIsOpen(true);
            setHighlightedIndex(-1);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => {
            onChange(query);
            setIsOpen(false);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={`${className} pr-8`}
        />
```

**3.** `selectOption` (further down, unchanged code shown for context only — no edit needed here,
since `setQuery(opt)` there is followed by the `useEffect` above resetting `hasTyped` to `false`
the next time `value` changes as a result of the selection propagating back through `onChange` ->
parent -> new `value` prop):

```tsx
  const selectOption = (opt: string) => {
    setQuery(opt);
    onChange(opt);
    setIsOpen(false);
    setHighlightedIndex(-1);
  };
```

Leave this function exactly as-is — do not add `setHasTyped` here. Do not touch it.

## Tests

Add to `web/components/projects/__tests__/ReviewGrid.test.tsx`. The existing test
`"renders AutocompleteInput and calls onDestinationFieldChange when option is selected"` (lines
113-152 as of this writing) is the exact reference pattern — same `testProps` shape, same
`screen.getByPlaceholderText("destination field...")` query to find the input, same
`fireEvent.focus`/`fireEvent.change` sequence. Copy its `testProps` object verbatim for the two new
tests below (it already has `destinationFields: ["id", "status_id", "name", "created_at"]` — 4
options, only 1 of which, `"id"`, is bound — sufficient to prove the bug).

Add these two new `it(...)` blocks in the same `describe("ReviewGrid", ...)` block as the existing
test above, right after it:

1. **New test:**

```tsx
  it("shows all destination field options when the picker is opened before typing", () => {
    const testProps = {
      ...props,
      editingEnabled: true,
      onDestinationFieldChange: vi.fn(),
      mappingTables: [
        {
          destinationTableName: "accounts",
          destinationFields: ["id", "status_id", "name", "created_at"],
          bindings: [
            {
              sourceField: "src_id",
              destinationField: "id",
              bindingType: "direct" as const,
            },
          ],
        },
      ],
    };

    render(<ReviewGrid {...testProps} />);
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    const input = screen.getByPlaceholderText("destination field...") as HTMLInputElement;
    fireEvent.focus(input);

    // Before this fix, only "id" (the current value) would appear here.
    expect(screen.getByText("status_id")).toBeInTheDocument();
    expect(screen.getByText("name")).toBeInTheDocument();
    expect(screen.getByText("created_at")).toBeInTheDocument();
  });
```

2. **New test:**

```tsx
  it("narrows destination field options once the user types", () => {
    const testProps = {
      ...props,
      editingEnabled: true,
      onDestinationFieldChange: vi.fn(),
      mappingTables: [
        {
          destinationTableName: "accounts",
          destinationFields: ["id", "status_id", "name", "created_at"],
          bindings: [
            {
              sourceField: "src_id",
              destinationField: "id",
              bindingType: "direct" as const,
            },
          ],
        },
      ],
    };

    render(<ReviewGrid {...testProps} />);
    fireEvent.click(screen.getByRole("button", { name: /accounts/ }));

    const input = screen.getByPlaceholderText("destination field...") as HTMLInputElement;
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "stat" } });

    expect(screen.getByText("status_id")).toBeInTheDocument();
    expect(screen.queryByText("name")).not.toBeInTheDocument();
    expect(screen.queryByText("created_at")).not.toBeInTheDocument();
  });
```

3. Run the full existing test file after these additions. The pre-existing test
   `"renders AutocompleteInput and calls onDestinationFieldChange when option is selected"` (lines
   113-152) must still pass unchanged — it already does `fireEvent.focus` then
   `fireEvent.change(input, { target: { value: "stat" } })` then selects `"status_id"` from the
   list, which remains correct under the fix (the `hasTyped` flag becomes `true` the moment
   `fireEvent.change` fires, narrowing the list to `"status_id"` exactly as that test expects).

## Verification

```bash
cd web && npx tsc --noEmit
```
Expect: no new type errors (compare against the pre-existing baseline the same way prior tasks in
this session did, via `git stash`/`git checkout HEAD~1` on just this file, if any errors appear —
don't assume any error you see is new without checking).

```bash
cd web && npx vitest run components/projects/__tests__/ReviewGrid.test.tsx
```
Expect: all tests pass, including the 2 new ones and every pre-existing test in this file.

```bash
cd web && npx vitest run
```
Expect: full suite passes, same count as before plus the 2 new tests.

## Pitfalls

- **Do not remove or weaken the `useEffect(() => { setQuery(value); }, [value])` sync** — it's
  still required for the picker to display the right current value when `value` changes externally
  (e.g. after a save). Only add `setHasTyped(false)` alongside it, don't replace it.
- **`hasTyped` must reset on every `value` change, not just once.** If a user opens the picker,
  types (narrowing the list), then blurs without selecting (which calls `onChange(query)` — see the
  `onBlur` handler), and the parent doesn't actually change `value` in response (e.g. an invalid
  entry is rejected upstream), `hasTyped` would stay `true` until `value` does change. This is
  correct, expected behavior — don't try to reset `hasTyped` from anywhere except the `[value]`
  effect.
- **Don't touch `selectOption`.** It's tempting to add `setHasTyped(false)` there directly for
  clarity, but `value` and the component's `query`/`hasTyped` state are driven by the parent
  re-rendering with a new `value` prop after `onChange` fires — adding a second, redundant reset
  path risks a subtle race depending on render timing. The existing `[value]` effect is the single
  source of truth for this reset; keep it that way.
- This bug and fix are entirely local to `AutocompleteInput` inside `ReviewGrid.tsx` — confirm
  before starting that no other file defines or imports a component by this name
  (`grep -rn "AutocompleteInput" web --include="*.tsx"` should only show `ReviewGrid.tsx` and its
  test file).

## Commit

Own commit. Suggested message: `fix: show all destination field options when picker opens, not
just the current value (001eo)`.
