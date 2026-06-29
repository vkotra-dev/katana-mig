# Katana — design tokens (canonical)

**Canonical primary:** `#3525cd` (deep indigo). Use this for primary action buttons,
active nav indicators, and focus rings. `#4f46e5` is `primary-container` (the lighter
tint used for chip backgrounds / hover fills) — it is **not** the primary action color.

Stitch keeps a **per-project theme**, so screens generated in the *same* Stitch
project inherit this automatically — you normally do NOT need to re-paste this.
Keep it here as the canonical reference, and paste it at the top of a prompt only
if a screen comes back visually off-theme (e.g. buttons rendering as `#4f46e5` purple
instead of `#3525cd` indigo).

```html
<script id="tailwind-config">
  tailwind.config = {
    darkMode: "class",
    theme: { extend: {
      colors: {
        primary: "#3525cd",            // CANONICAL indigo — primary actions, active nav
        "primary-container": "#4f46e5", // lighter tint — chip backgrounds, hover fills only
        secondary: "#4648d4",
        "secondary-container": "#6063ee",
        background: "#f8f9fa",
        surface: "#f8f9fa",
        "surface-container-low": "#f3f4f5",
        "surface-container": "#edeeef",
        "surface-container-high": "#e7e8e9",
        "surface-container-highest": "#e1e3e4",
        "on-surface": "#191c1d",
        "on-surface-variant": "#464555",
        outline: "#777587",
        "outline-variant": "#c7c4d8",
        error: "#ba1a1a"
        // status: use green=complete/approved, amber/tertiary=action-required/paused,
        // error(red)=failed/blocked, blue/secondary=in-progress, gray=idle/queued
      },
      spacing: { "sidebar-width": "240px", "container-padding": "16px",
                 "element-gap": "8px", gutter: "12px", unit: "4px" },
      fontFamily: { display: ["Inter"], body: ["Inter"], code: ["JetBrains Mono"] },
      borderRadius: { DEFAULT: "0.125rem", lg: "0.25rem", xl: "0.5rem", full: "0.75rem" }
    } }
  }
</script>
```

Row height for data tables: **38px**. Body text Inter 13–14px. IDs / versions /
timestamps in JetBrains Mono with a copy icon.
