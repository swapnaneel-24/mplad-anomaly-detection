# PEIARS Frontend Design System

**Version:** PR-05A redesign (desktop scientific workbench)
**Applies to:** `frontend/` React + TypeScript + Vite application
**Governing philosophy:** A (Editorial Research Journal, 25%) + 2B (Scientific Analysis Workbench, 50%, dominant) + C (Institutional Investigation Casebook, 25%)

This document is the authoritative source for visual tokens, typography, layout,
interaction and accessibility rules. The PR-05A redesign replaces the previous
permanent left-sidebar dashboard with a **desktop-only horizontal workspace
switcher** and **purpose-specific multi-panel compositions** per workspace.

---

## 1. Visual identity rationale (unchanged)

PEIARS is a scientific investigation workbench. The visual identity is **not**
a generic SaaS dashboard. The redesign preserves the existing palette and
typographic personality while fundamentally restructuring the post-login
layout. Three influences govern the look:

* **Editorial Research Journal (A, 25%)** — serif headings, generous
  whitespace at the page level, figure/table captions, methodological
  annotations. Used selectively for narrative surfaces (Overview lede,
  Research methodology).
* **Scientific Analysis Workbench (2B, 50%, dominant)** — multi-panel
  analytical layouts, dense data tables, parameter rails, central canvases,
  record inspectors. The dominant post-login experience.
* **Institutional Investigation Casebook (C, 25%)** — structured case views,
  evidence inspectors, chronological history, actor provenance.

### What changed in the redesign

* **Removed:** permanent 240px left sidebar, mobile hamburger drawer,
  generic dashboard header, repetitive single-column page compositions.
* **Added:** compact horizontal workspace switcher, contextual strip per
  workspace, multi-panel compositions (canvas + rails + inspectors),
  provenance footer, desktop-minimum-width gate.
* **Preserved:** colour palette, typography, login screen, authentication,
  CSRF, session restoration, typed API client, six conceptual workspaces.

### What this is *not* (still)

Not a teal SaaS dashboard. Not four KPI cards in a row. Not a hero with a
gradient. Not glassmorphism. Not animated illustrations. Not invented
performance statistics. Not a generic admin template.

---

## 2. Colour tokens (unchanged)

All colors are defined as CSS custom properties on `:root` in
`src/styles/tokens.css`. Components reference tokens by name only.

### 2.1 Surface and text

| Token | Value | Role |
|---|---|---|
| `--color-bg` | `#f6f3ec` | Warm neutral primary background (paper) |
| `--color-bg-raised` | `#fbf9f3` | Raised surface (panels, inputs) |
| `--color-bg-sunken` | `#ece8de` | Sunken surface (table head, code blocks, context strips) |
| `--color-bg-inset` | `#e3dfd2` | Inset / active surface (active switcher tab) |
| `--color-border` | `#c9c3b1` | Cool-grey primary divider |
| `--color-border-strong` | `#8f8a78` | Strong divider (panel separation) |
| `--color-text` | `#1f2630` | Deep slate primary text (graphite) |
| `--color-text-muted` | `#515966` | Secondary text (captions, metadata) |
| `--color-text-faint` | `#7a8088` | Tertiary text (placeholder, disabled) |

### 2.2 Accent (analytical selection / navigation)

| Token | Value | Role |
|---|---|---|
| `--color-accent` | `#1f5d5a` | Muted teal — active switcher tab, focused input ring, primary action |
| `--color-accent-hover` | `#174a48` | Hover state for primary action |
| `--color-accent-soft` | `#d6e3e0` | Soft teal background for active switcher tab |
| `--color-accent-line` | `#3c807c` | Subtle accent line (active tab underline) |

### 2.3 Semantic

| Token | Value | Role |
|---|---|---|
| `--color-success` | `#3a6b3e` | Forest green (status: ready, verified) |
| `--color-success-soft` | `#dde7d8` |
| `--color-warning` | `#9c6b1f` | Soft ochre (status: not_ready, caution) |
| `--color-warning-soft` | `#efe1c8` |
| `--color-error` | `#8a2a2a` | Deep red (status: unreachable, error) |
| `--color-error-soft` | `#efd8d8` |
| `--color-info` | `#3a5878` | Slate blue (informational metadata) |

### 2.4 Status mapping (system connectivity)

| Logical status | Foreground | Background | Label |
|---|---|---|---|
| `ready` | `--color-success` | `--color-success-soft` | "Ready" |
| `not_ready` | `--color-warning` | `--color-warning-soft` | "Not ready" |
| `unreachable` | `--color-error` | `--color-error-soft` | "Unreachable" |
| `unknown` | `--color-text-muted` | `--color-bg-sunken` | "Unknown" |

### 2.5 Contrast

Every text/background combination meets **WCAG AA** (4.5:1 for body text,
3:1 for large text and UI components). Verified ratios unchanged from the
prior delivery.

---

## 3. Typography system (unchanged)

### 3.1 Font stacks

No font files are bundled.

```css
--font-editorial: "Source Serif 4", "Source Serif Pro", "Charter",
                  "Iowan Old Style", Georgia, "Times New Roman", serif;
--font-interface: "Inter", "SF Pro Text", "Segoe UI", "Roboto",
                  "Helvetica Neue", system-ui, sans-serif;
--font-mono:      "JetBrains Mono", "SF Mono", "Menlo", "Consolas",
                  "DejaVu Sans Mono", monospace;
```

### 3.2 Type scale (modular, 1.125 ratio)

| Token | Size | Line height | Use |
|---|---|---|---|
| `--font-size-xs` | 11px | 1.45 | Caption / metadata / switcher tab subtext |
| `--font-size-sm` | 13px | 1.5 | Secondary labels, switcher tabs, table headers |
| `--font-size-base` | 15px | 1.6 | Body text, default |
| `--font-size-md` | 17px | 1.5 | Card headings, sub-section headings |
| `--font-size-lg` | 21px | 1.4 | Workspace page H2 (in-context strip) |
| `--font-size-xl` | 28px | 1.25 | Workspace page H1 (serif, editorial) — used sparingly |
| `--font-size-2xl` | 36px | 1.2 | Login title only |

### 3.3 Numerals

* `font-variant-numeric: tabular-nums` on all `--font-mono` text and
  numerical table cells.

### 3.4 Weight

Three weights: `400`, `500`, `700`.

---

## 4. Spacing scale (unchanged)

Base `4px`. Scale: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80`.

```css
--space-1:  4px;
--space-2:  8px;
--space-3:  12px;
--space-4:  16px;
--space-5:  20px;
--space-6:  24px;
--space-8:  32px;
--space-10: 40px;
--space-12: 48px;
--space-16: 64px;
--space-20: 80px;
```

---

## 5. Layout grid (REDESIGNED)

### 5.1 Desktop application shell — horizontal workspace switcher

The permanent left sidebar is **removed**. The post-login shell is a
vertical stack of horizontal bands:

```
+--------------------------------------------------------------------------+
| IDENTITY BAR (40px)                                                      |
| PEIARS  ·  Anomaly Review Workbench           env · api · user · sign out|
+--------------------------------------------------------------------------+
| WORKSPACE SWITCHER (36px)                                                |
| Overview │ Data │ Analysis │ Investigations │ Domains │ Research         |
+--------------------------------------------------------------------------+
| CONTEXT STRIP (32px)                                                     |
| <workspace>  /  <dataset context>  /  <method/snapshot context>          |
+--------------------------------------------------------------------------+
|                                                                          |
|  WORKSPACE-SPECIFIC COMPOSITION (flexible, fills remaining height)       |
|                                                                          |
|  Each workspace defines its own panel grid (see SCREEN_DESIGN_NOTES.md)  |
|                                                                          |
+--------------------------------------------------------------------------+
| PROVENANCE FOOTER (24px)                                                 |
| api status · app version · git commit · request id (on error)            |
+--------------------------------------------------------------------------+
```

* **Identity bar** — `40px` tall, sticky. PEIARS serif mark + subtitle on
  the left; environment name, connectivity pill, user display name + role,
  Sign out button on the right. Single line; no duplicate page title here.
* **Workspace switcher** — `36px` tall, sticky. Six horizontal tabs with
  the workspace short name. Active tab: `--color-accent-soft` background,
  `2px` `--color-accent` bottom border, `--color-text` foreground,
  `font-weight: 500`, `aria-current="page"`. Inactive: transparent
  background, `--color-text-muted` foreground, hover `--color-bg-sunken`.
  Keyboard-accessible (Tab to move, Enter/Space to activate, Arrow Left/
  Right to move between tabs per WAI-ARIA tabs pattern).
* **Context strip** — `32px` tall, `--color-bg-sunken` background, `1px`
  `--color-border` bottom border. Shows the current workspace name +
  contextual breadcrumb (dataset, snapshot, method) in `--font-mono`,
  `--font-size-xs`, `--color-text-muted`. Left-aligned. The right side
  may carry workspace-specific contextual actions in a later PR.
* **Workspace composition** — flexible; fills remaining viewport height.
  Each workspace defines its own grid (see §6 and SCREEN_DESIGN_NOTES.md).
  Internal scroll per panel; the shell itself does not scroll vertically.
* **Provenance footer** — `24px` tall, `--color-bg-sunken` background,
  `1px` `--color-border` top border. API status pill, app version, git
  commit (or `not supplied`), all in `--font-mono`, `--font-size-xs`,
  `--color-text-faint`. On error: the request ID is shown here in
  `--color-error`.

### 5.2 Sidebar dimensions (REMOVED)

There is no sidebar. The previous `--sidebar-width: 240px` and
`--sidebar-collapsed-width: 56px` tokens are removed from the active
stylesheet (kept in tokens.css as deprecated documentation with a comment).

### 5.3 Responsive behaviour (REDESIGNED — desktop-only)

**PEIARS is exclusively a desktop/laptop application.** There is no mobile
layout, no hamburger, no drawer, no collapsed icon rail.

| Viewport width | Behaviour |
|---|---|
| `< 1024px` | **Unsupported.** A full-viewport gate panel replaces the application: "This analytical workbench requires a desktop-sized window (at least 1024 CSS pixels wide). Widen your browser window or use a desktop monitor." The gate is restrained (editorial serif heading, muted body text, no illustration). |
| `1024–1365px` | Minimum supported (PR-06A normalized minimum; earlier revisions said 1280). Workspace compositions use their compact grid variants (narrower rails, tighter gutters). No horizontal scrolling. |
| `1366–1439px` | Target (1366×768 laptop). Full multi-panel compositions. |
| `1440–1919px` | Target (1440×900 laptop). Full multi-panel compositions. |
| `≥ 1920px` | Target (1920×1080 desktop). Full multi-panel compositions; the central canvas in Analysis expands to use the extra width. |

The layout accommodates different supported monitor sizes and browser zoom
levels via CSS `grid-template-columns` with `minmax()` and `fr` units — not
fixed pixel positioning. Panels use `min-width: 0` so they shrink rather
than overflow.

### 5.4 Desktop-minimum-width gate

A `<DesktopGate>` component wraps the authenticated application. It checks
the window width against the exported `DESKTOP_MIN_WIDTH` constant (1024,
the PR-06A normalized minimum) on resize. When the width is below the
minimum, it renders the gate panel instead of `<AppShell>`. The gate:

* Does **not** hide the workspace switcher or identity bar (the user is
  still authenticated); it hides the **workspace composition** area and
  replaces it with the width message.
* Is announced to screen readers via `role="alert"`.
* Re-evaluates on resize (debounced 150ms).

---

## 6. Workspace panel grids (NEW)

Each workspace defines its own CSS grid. The grids are **not** shared.
This is the core of the redesign: purpose-specific compositions, not a
generic page template.

### 6.1 Overview — Research Index

Asymmetric editorial composition. Single column, max-width `960px`,
centered within the composition area. Internal sections use a 2-column
`240px 1fr` grid for label/value definition lists. A compact "research
workflow map" strip sits at the top — a horizontal row of phase labels
(Phase 3 → Phase 4 → Phase 5 → Phase 6) connected by `→` glyphs in
`--font-mono`, with the current integration state under each.

### 6.2 Data Observatory — Dataset Examination

Three-column grid: `240px 1fr 320px`.
* Left (240px): contextual filter rail (compact, scrollable).
* Centre (1fr): main source-examination table.
* Right (320px): source-metadata inspector (deferred content in PR-05A).

### 6.3 Anomaly Analysis — Primary Scientific Workbench

Four-region grid filling the composition area:
```
+----------------+----------------------------------+----------------+
| PARAMETER RAIL |                                  | INSPECTOR      |
| (220px)        |       CENTRAL ANALYTICAL         | (300px)        |
|                |       CANVAS (1fr)               |                |
|                |                                  |                |
+----------------+----------------------------------+----------------+
| EVIDENCE / RECORDS TABLE (full width, 220px tall, scrollable)        |
+----------------------------------------------------------------------+
```
The central canvas visually dominates. The grid is
`grid-template-columns: 220px 1fr 300px; grid-template-rows: 1fr 220px;`
with the evidence table spanning all three columns on the bottom row.

### 6.4 Investigation Workspace — Evidence Casebook

Two-column split-pane:
```
+--------------------+----------------------------------+--------------+
| CASE INDEX         | EVIDENCE / DOCUMENT              | ASSESSMENT   |
| (260px, scrollable)| WORKSPACE (1fr)                  | + HISTORY    |
|                    |                                  | (320px)      |
+--------------------+----------------------------------+--------------+
```
Grid: `260px 1fr 320px`. The evidence workspace is the primary surface;
the case index is a selectable list; the assessment panel shows review
state + chronological history.

### 6.5 Cross-Domain Study — Comparative Research

Three-column comparison grid `repeat(3, 1fr)` with a top "comparison
axis" strip (96px tall) that labels the columns. Each column is a
structured domain card with a `<dl>` of verified facts (not a marketing
card). Below the three columns: a full-width "comparability matrix" table.

### 6.6 Research & Provenance — Reproducibility

Two-column grid `1fr 320px`:
* Left (1fr): methodological sections (Phase 3 → Phase 6) as a vertical
  narrative with figure-caption-style annotations.
* Right (320px): sticky artifact index + reproducibility checklist +
  limitations list.

---

## 7. Table and figure conventions (refined)

### 7.1 Tables

* Header row: `--color-bg-sunken`, `--color-text-muted`, `--font-size-xs`,
  `font-weight: 500`, `text-transform: uppercase`, `letter-spacing: 0.04em`,
  `padding: var(--space-2) var(--space-3)`.
* Body rows: `--color-bg-raised`, `1px` `--color-border` bottom border.
  Hover: `--color-bg-sunken`.
* Body cells: `--font-size-sm`, `padding: var(--space-2) var(--space-3)`.
  Numeric cells: `--font-mono`, `text-align: right`, `tabular-nums`.
* Selected row (where applicable): `--color-accent-soft` background,
  `2px` `--color-accent` left border.
* Empty state: single centered row spanning all columns, honest message.

### 7.2 Figures / analytical canvases

PR-05A has no real figures. The reserved analytical canvas in the Anomaly
Analysis workspace:

* `1px` dashed `--color-border-strong` border, `--color-bg-raised` background.
* A centered label `Analytical canvas — not yet integrated` in
  `--font-editorial`, `--font-size-md`, italic, `--color-text-muted`.
* Below the label: a one-sentence description of the future intent in
  `--font-size-sm`, `--color-text-faint`, `--font-mono`.
* The canvas **does not** contain dozens of empty outlined boxes. It is
  a single honest surface.

### 7.3 Captions

Captions sit **above** tables and **below** figures. Caption style:
`--font-interface`, `--font-size-xs`, `--color-text-muted`. Caption text
begins with `Table N.` / `Figure N.` in `--font-mono`.

---

## 8. Button and input conventions (unchanged)

Three button variants: `primary`, `secondary`, `ghost`. Heights `36px`
(default) / `32px` (compact, used in the identity bar's Sign out).
Focus: `2px` `--color-accent` outline offset `2px`. Transitions limited to
`background-color` and `color`, max `120ms`.

Inputs: `36px` height, `--color-bg-raised` background, `1px` `--color-border`
border, `:focus` border `--color-accent` + `2px` `--color-accent-soft` ring.

---

## 9. Loading, error, empty and unavailable states (refined)

### 9.1 Loading

* **Inline**: button label → `Working…`, `aria-busy="true"`, disabled.
* **Block / panel**: single centered `Loading…` in `--color-text-muted`,
  `--font-size-sm`, `aria-busy="true"`. No skeleton shimmer.
* **Workspace composition**: the context strip shows `Loading…` while the
  workspace's primary fetch is in flight; the composition area shows a
  centered `Loading…` line.

### 9.2 Error

* **Inline form error**: helper text below the field, `--color-error`.
* **Block / panel error**: `--color-error-soft` background panel with `4px`
  `--color-error` left border. Sanitized message + request ID in mono.
  No stack traces.
* **Provenance footer**: on error, the request ID appears in `--color-error`.

### 9.3 Empty

Centered single line, `--color-text-muted`, `--font-size-sm`. Honest
message (e.g. `No sources registered.`).

### 9.4 Unavailable (deferred functionality)

`DeferredPanel` component: `--color-bg-raised` background, `1px` dashed
`--color-border-strong` border, italic heading `Not available in this
release`, one-sentence description, optional future-PR tag in mono. Used
**within** the intended layout (e.g. the right-side inspector in Data
Observatory is a DeferredPanel — the layout still shows the three-column
structure, not a blank page).

---

## 10. Interaction principles (refined)

1. **No gratuitous animation.** Transitions limited to color and opacity,
   max `150ms`. No slide-in panels, no fade-and-scale modals.
2. **Keyboard first.** The workspace switcher follows the WAI-ARIA tabs
   pattern: Tab to enter, Arrow Left/Right to move, Enter/Space to
   activate, Tab to leave. Every interactive element has a visible focus
   ring.
3. **No double submission.** Action buttons enter `Working…` on click.
4. **No content flash.** Protected routes render `Loading…` until
   `/auth/me` resolves.
5. **Network failure is uncertainty, not logout.** Only an explicit `401`
   clears the session.
6. **Respect `prefers-reduced-motion`.** All transitions set to `0ms`.
7. **Desktop-only.** No mobile interactions, no swipe gestures, no
   long-press affordances.

---

## 11. Accessibility requirements (refined)

* **WCAG 2.1 AA** target.
* **Semantic HTML.** `<nav>` for the switcher, `<main>` for the composition,
  `<footer>` for the provenance bar.
* **Heading hierarchy.** Each workspace composition has exactly one `<h1>`
  (the workspace name in the context strip). Section headings within a
  composition are `<h2>`; sub-sections `<h3>`. The identity bar's PEIARS
  mark is a `<span>` (it is not a page heading).
* **Focus management.** Route changes move focus to the workspace `<h1>`.
  The switcher manages roving tabindex.
* **ARIA.** `aria-current="page"` on the active switcher tab;
  `aria-busy="true"` on loading regions; `aria-live="polite"` on the
  connectivity pill and provenance footer.
* **Document title.** `document.title` = `<workspace> · PEIARS`.
* **Reduced motion.** `@media (prefers-reduced-motion: reduce)` sets all
  transitions to `0ms`.
* **Keyboard.** No keyboard traps. The switcher supports Arrow Left/Right
  per the WAI-ARIA tabs pattern.

---

## 12. Explicit anti-patterns to avoid (updated)

1. **Permanent left sidebar.** Removed in the redesign.
2. **Mobile hamburger drawer.** Removed. Desktop-only.
3. **Generic dashboard header with page title duplicated in three places.**
   The page title appears once (in the context strip).
4. **Repetitive single-column page compositions across all workspaces.**
   Each workspace has its own panel grid.
5. **Four generic KPI cards in a row.** Forbidden.
6. **Bright blue-purple gradient branding.** Forbidden.
7. **Giant greeting banners.** Forbidden.
8. **Generic hero illustrations.** Forbidden.
9. **Excessive rounded rectangles.** Border radius `4px` for inputs and
   buttons, `0` for panels and tables.
10. **Decorative glassmorphism.** No `backdrop-filter`.
11. **Gratuitous animations.** No fade-in-up, no scale-on-hover, no
    shimmer.
12. **Arbitrary dashboard charts.** No chart libraries, no fake sparklines.
13. **Invented performance statistics.** No fabricated numbers.
14. **Decorative AI icons.** No sparkle icons, no robot icons.
15. **Stock photos.** None.
16. **Meaningless progress bars.** No `Loading 47%`.
17. **Fake live-system indicators.** No pulsing green dot.
18. **Greyed-out fake controls.** Deferred functionality uses honest
    `DeferredPanel`s.
19. **Raw stack traces in the UI.** Sanitized message + request ID only.
20. **Session tokens in `localStorage`/`sessionStorage`.** HttpOnly cookie
    only.
21. **Logging credentials or cookies.** Request ID and status only.
22. **Dozens of empty outlined boxes in a deferred canvas.** The Analysis
    canvas is a single honest surface, not a grid of empty placeholders.
23. **Three generic marketing cards in Cross-Domain Study.** Structured
    `<dl>` of verified facts per domain, not a card grid.
24. **Mobile-specific CSS at `< 768px`.** The desktop gate handles narrow
    viewports; no mobile layout exists.
