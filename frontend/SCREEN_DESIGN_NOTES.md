# PEIARS Screen Design Notes — PR-05A Redesign

**Companion to:** `frontend/DESIGN_SYSTEM.md`
**Scope:** PR-05A redesign — desktop-only horizontal workspace switcher + multi-panel compositions
**Governing philosophy:** A (Editorial, 25%) + 2B (Workbench, 50%, dominant) + C (Casebook, 25%)

This document describes the redesigned layout for each screen. The previous
permanent-left-sidebar dashboard is replaced. Each workspace now has a
purpose-specific multi-panel composition.

---

## 1. Login screen (`/login`) — UNCHANGED

The login screen is preserved exactly as designed in the prior PR-05A
delivery. Single-column centered, max-width 420px. Serif PEIARS identity
block, editorial lede, form (username + password + Show/Hide toggle),
connectivity hint. See the prior `SCREEN_DESIGN_NOTES.md` §1 for the full
composition.

**Why unchanged:** the redesign prompt explicitly preserves the
"login-screen design language" (§2). The login screen never had the
sidebar/dashboard problem.

---

## 2. Application shell — REDESIGNED

The post-login shell is a vertical stack of horizontal bands (see
`DESIGN_SYSTEM.md` §5.1). No left sidebar. No mobile drawer.

### 2.1 Identity bar (40px, sticky)

```
PEIARS · Anomaly Review Workbench          development · ● Ready · Review One · REVIEWER · [Sign out]
```

* Left: `PEIARS` in `--font-editorial`, `--font-size-md`, weight 700. A
  middle-dot separator, then `Anomaly Review Workbench` in
  `--font-interface`, `--font-size-xs`, `--color-text-faint`.
* Right: environment name in mono xs; connectivity pill; user display
  name in sm medium; role in mono xs uppercase; `Sign out` secondary
  compact button.
* The identity bar does **not** repeat the page title. The page title
  appears once, in the context strip.

### 2.2 Workspace switcher (36px, sticky)

```
Overview │ Data │ Analysis │ Investigations │ Domains │ Research
```

* Six horizontal tabs. Each tab is a `<button>` (not a link — the switcher
  uses `useNavigate` on activation) styled as a tab.
* Active tab: `--color-accent-soft` background, `2px` `--color-accent`
  bottom border, `--color-text` foreground, `font-weight: 500`,
  `aria-current="page"`.
* Inactive: transparent background, `--color-text-muted` foreground, hover
  `--color-bg-sunken`.
* Keyboard: WAI-ARIA tabs pattern. Tab to enter the switcher, Arrow
  Left/Right to move focus between tabs, Enter/Space to activate, Tab to
  leave into the composition.
* The switcher is a `<nav aria-label="Workspace switcher">` containing a
  `<div role="tablist">`.

### 2.3 Context strip (32px, sticky)

```
Study Overview  /  dataset: none registered  /  method: unsupervised (frozen)
```

* `--color-bg-sunken` background, `1px` `--color-border` bottom border.
* Content: workspace name (the page H1, in `--font-interface`,
  `--font-size-sm`, weight 500) + contextual breadcrumb in `--font-mono`,
  `--font-size-xs`, `--color-text-muted`.
* The breadcrumb is workspace-specific:
  - Overview: `dataset: none registered / method: unsupervised (frozen)`
  - Data: `dataset: source registry / records: <count>`
  - Analysis: `dataset: none registered / model: Isolation Forest + LOF (deferred)`
  - Investigations: `cases: <count> / status: deferred`
  - Domains: `comparison: ULB · PMGSY · MPLADS`
  - Research: `pipeline: frozen / tests: 445`
* Right side (reserved): workspace-specific contextual actions (empty in
  PR-05A; will host e.g. "New case" in PR-05B).

### 2.4 Workspace composition (flexible)

Each workspace defines its own grid (see §3–§8 below). The composition
fills the remaining viewport height. Internal panels scroll independently;
the shell itself does not scroll vertically.

### 2.5 Provenance footer (24px, sticky)

```
API: ● Ready · v0.4.0 · git: not supplied
```

* `--color-bg-sunken` background, `1px` `--color-border` top border.
* Content: `API:` + status pill + `·` + app version + `·` + git commit
  (or `not supplied`), all in `--font-mono`, `--font-size-xs`,
  `--color-text-faint`.
* On error: `· request: <id>` appended in `--color-error`.

---

## 3. Overview — Research Index (`/overview`)

**Purpose:** structured scientific entry point. Editorial voice (A) is
strongest here, but the workbench (2B) appears in the verified status
panels.

**Composition:** single column, max-width 960px, centered within the
composition area. Internal sections use a `240px 1fr` label/value grid.

**Layout (top to bottom):**

1. **Study heading** — `<h1>` `MPLAD Fund-Utilisation Anomaly Pattern
   Detection` in `--font-editorial`, `--font-size-xl`, weight 700.
   Subtitle `Using Unsupervised Learning` in `--font-editorial`,
   `--font-size-md`, `--color-text-muted`.
2. **Research problem statement** — 2 short paragraphs in
   `--font-editorial`, `--font-size-base`. States the academic question,
   the evidence-bound stance ("an anomaly flag never implies fraud"),
   and that the pipeline is frozen.
3. **Research workflow map** — a horizontal strip, `--color-bg-sunken`
   background, `1px` `--color-border`, `48px` tall. Four phase labels in
   `--font-mono`, `--font-size-xs`:
   ```
   Phase 3 · feature engineering  →  Phase 4 · model fitting  →  Phase 5 · analysis  →  Phase 6 · synthesis
   ```
   Under each: a one-line integration state in `--color-text-faint`
   (`frozen · tests green` for Phase 3–6). This is a methodological
   annotation, not a fake progress bar.
4. **Research streams** — two columns (`1fr 1fr`):
   - Left: `Stream A — ULB benchmark` with a one-paragraph description
     (verified benchmark, Phase 3–5).
   - Right: `Stream B — Cross-domain feasibility` with a one-paragraph
     description (PMGSY/MPLADS exploratory, not yet integrated).
5. **Verified application status** — `<h2>` `Application status` + a
   `<dl>` in `240px 1fr` grid: API version, git commit, environment,
   liveness, readiness (with per-check pills). All values from `/meta`
   and `/health/*`.
6. **Subsystem availability** — `<h2>` + a `<table>` (Caption: `Table 1.
   Subsystem state as reported by /api/v1/meta.`) Columns: Subsystem,
   State. Rows from `MetaResponse.subsystems`.
7. **Workspace entry points** — `<h2>` `Workspaces` + a 2×3 grid of
   compact entry cards. Each card: workspace number + name + one-line
   purpose + a `<link>` to the workspace. **Not** a KPI card — no
   numbers, no charts. Just a navigational index with editorial labels.

**Why this reflects A + 2B + C:**
- *A* — serif heading, editorial problem statement, methodological
  workflow map with phase labels.
- *2B* — verified status `<dl>`, subsystem table, workspace entry index.
- *C* — honest separation of implemented vs deferred, provenance
  metadata in the workflow map.

---

## 4. Data Observatory (`/data`) — Dataset Examination

**Purpose:** dataset exploration and provenance. Workbench-dominant (2B).

**Composition:** three-column grid `240px 1fr 320px`, filling the
composition area. Each column scrolls independently.

**Layout:**

1. **Left rail (240px) — Contextual filters**
   * `<h2>` `Filters` in `--font-size-sm`, weight 500.
   * Three filter groups, each a `<fieldset>`:
     - Dataset kind (radio: any / ULB / PMGSY / MPLADS)
     - Integrity status (radio: any / verified / unverified_legacy / ...)
     - Analysis status (radio: any / verified_benchmark / exploratory / ...)
   * **PR-05A honesty:** the radios are present and styled, but they are
     `disabled` because the source registry is empty. A small note under
     each fieldset in `--color-text-faint`, `--font-size-xs`:
     `Filtering requires registered sources.` The disabled state is
     honest — not greyed-out fake interactivity, but clearly labelled
     disabled controls with a reason.
2. **Centre (1fr) — Source examination table**
   * Caption: `Table 2. Registered data sources (/api/v1/sources).`
   * Columns: Source ID, Dataset kind, Integrity, Analysis.
   * Rows from `SourceListResponse.sources`. Empty state:
     `No sources registered. The source registry is empty.`
   * Below the table: a compact `<h3>` `Registry semantics` + 2-sentence
     paragraph (server-side, opaque slugs, no filesystem scanning).
3. **Right inspector (320px) — Source metadata**
   * `<h2>` `Source metadata` in `--font-size-sm`, weight 500.
   * **PR-05A honesty:** a `DeferredPanel` with title `Source metadata
     inspector (deferred)`, description `Field definitions, schema
     provenance and integrity reports will appear here when a source is
     selected.`, futurePr `PR-05B`.
   * The inspector is part of the layout (the three-column structure is
     visible), not a blank page.

---

## 5. Anomaly Analysis (`/analysis`) — Primary Scientific Workbench

**Purpose:** the strongest visual expression of the workbench (2B). The
central analytical canvas dominates.

**Composition:** four-region grid filling the composition area:
```
grid-template-columns: 220px 1fr 300px;
grid-template-rows: 1fr 220px;
```
- Top-left: parameter rail (220px).
- Top-centre: central analytical canvas (1fr, spans the row).
- Top-right: observation/interpretation inspector (300px).
- Bottom: evidence/records table (spans all 3 columns, 220px tall).

**Layout:**

1. **Parameter rail (220px, top-left) — `<h2>` `Parameters`**
   * A `<form>` with disabled fieldsets (PR-05A honesty):
     - `Detector` (select: Isolation Forest / LOF / both — disabled)
     - `Contamination` (range slider — disabled)
     - `Feature subset` (multi-select — disabled)
     - `Random seed` (number input — disabled)
   * Each disabled control has a small `PR-05B` tag in mono.
   * Below the form: a `DeferredPanel`-style note `Parameter sweeps will
     drive the central canvas once the research-evidence service is
     integrated.`
2. **Central canvas (1fr, top-centre) — `<h2>` `Analytical canvas`**
   * A single large panel with `1px` dashed `--color-border-strong`
     border, `--color-bg-raised` background.
   * Centered content:
     - `Analytical canvas — not yet integrated` in `--font-editorial`,
       `--font-size-md`, italic, `--color-text-muted`.
     - One-sentence description in `--font-mono`, `--font-size-xs`,
       `--color-text-faint`: `Coordinated anomaly-score, PCA and detector-
       agreement plots will render here for the selected dataset and
       parameters.`
     - A small `Figure 1 (deferred)` caption below.
   * **The canvas is a single honest surface, not a grid of empty boxes.**
3. **Inspector (300px, top-right) — `<h2>` `Observation`**
   * A `DeferredPanel` with title `Selected-observation inspector
     (deferred)`, description `Feature values, anomaly score, neighbour
     context and reviewer notes for the selected record will appear here.`
   * Below: a static `<h3>` `Intended fields` + a `<ul>` of field names
     in mono (`record_id`, `anomaly_score`, `detector_consensus`,
     `feature_contributions`, `reviewer_note`). This documents the
     future shape without faking data.
4. **Evidence table (bottom, full width, 220px) — `<h2>` `Records`**
   * Caption: `Table 3. Anomaly records (deferred).`
   * Columns: Record ID, Dataset, Detector, Score, Rank, Review status.
   * **PR-05A honesty:** the table renders with headers but the body is
     a single row: `<EmptyState>No records available. The research-
     evidence service is not yet integrated.</EmptyState>`

**Why this reflects 2B dominance:** the central canvas occupies the
largest area. The parameter rail and inspector are genuinely useful
analytical affordances (reserved, not fake). The evidence table anchors
the bottom. This is the layout of a scientific instrument console.

---

## 6. Investigation Workspace (`/investigations`) — Evidence Casebook

**Purpose:** human review and case management. Casebook-dominant (C).

**Composition:** three-column grid `260px 1fr 320px`, filling the
composition area.

**Layout:**

1. **Case index (260px, left) — `<h2>` `Cases`**
   * A scrollable list area with a compact table header (Case ID, Status).
   * **PR-05A honesty:** the list body is an `EmptyState`: `No cases
     available. Case management is deferred to PR-05B.`
   * Above the list: a disabled `New case` button (secondary, compact)
     with a `PR-05B` tag.
2. **Evidence workspace (1fr, centre) — `<h2>` `Evidence`**
   * A `DeferredPanel` with title `Evidence workspace (deferred)`,
     description `The selected case's evidence documents, anomaly
     references and reviewer annotations will appear here. Cases are
     append-only and attributed to authenticated reviewers.`
   * Below: a static `<h3>` `Case model` + a `<dl>` of the future case
     schema fields (`case_id`, `target_ref`, `status`, `created_by`,
     `actor_ref`, `version`, `events`). This documents the PR-03
     append-only case model without faking instances.
3. **Assessment + history (320px, right) — `<h2>` `Assessment`**
   * Top half: `DeferredPanel` `Assessment (deferred)` — `Reviewer
     conclusions, severity assignment and disposition will appear here.`
   * Bottom half: `DeferredPanel` `Event history (deferred)` — `The
     append-only case timeline (status transitions, evidence additions,
     reviewer comments) will appear here.`
   * A small `<h3>` `Attribution` note below: `Every event carries an
     actor_ref derived from the authenticated principal (user:<uuid>).
     Client-supplied actor fields are never trusted.`

**Why this reflects C:** the three-column split (index + evidence +
assessment/history) is the classic casebook layout. The case model `<dl>`
makes the append-only, attributed nature of future cases visible without
faking instances.

---

## 7. Cross-Domain Study (`/domains`) — Comparative Research

**Purpose:** ULB, PMGSY, MPLADS distinctions. Workbench (2B) + editorial (A).

**Composition:** a top comparison-axis strip (96px) + a three-column grid
`repeat(3, 1fr)` + a full-width comparability-matrix table below.

**Layout:**

1. **Comparison axis strip (96px, top)**
   * `--color-bg-sunken` background, `1px` `--color-border` bottom border.
   * Three equal cells, one per domain: domain name in `--font-editorial`,
    `--font-size-md`, weight 700; below it, the dataset kind slug in mono
    xs. Visually labels the three columns.
2. **Three-column comparison (`repeat(3, 1fr)`)**
   * Each column is a structured domain panel:
     - `<h3>` domain name
     - `<dl>` of verified facts: `Dataset kind slug` (mono), `Registered
       sources` (count from `/sources` filtered by kind), `Subsystem
       state` (from `/meta`), `Pipeline phase` (Phase 3–5 for ULB; `not
       integrated` for PMGSY/MPLADS).
     - A `<h4>` `Methodological status` + 2-sentence paragraph (ULB:
       verified benchmark; PMGSY/MPLADS: exploratory).
     - A `<h4>` `Known limitations` + `<ul>` of 2–3 honest limitations
       per domain.
   * **Not marketing cards** — structured `<dl>` of verified facts.
3. **Comparability matrix (full-width table, below)**
   * Caption: `Table 4. Cross-domain comparability matrix.`
   * Columns: Dimension, ULB, PMGSY, MPLADS.
   * Rows: `Unit of analysis`, `Coverage`, `Anomaly semantics`,
     `Feature comparability`, `Transfer constraints`.
   * Each cell is a short honest phrase (e.g. ULB `Unit of analysis` =
     `Urban local body`; PMGSY = `Road reach`; MPLADS = `Fund release`).
   * This matrix makes the non-comparability visible.

**Why this reflects A + 2B:** the comparison axis strip and structured
`<dl>`s are workbench density; the comparability matrix is the editorial
voice restraining the workbench's instinct to combine incomparable data.

---

## 8. Research & Provenance (`/research`) — Reproducibility

**Purpose:** methods, reproducibility, limitations, artifacts. Editorial (A)
+ casebook (C).

**Composition:** two-column grid `1fr 320px`.

**Layout:**

1. **Left column (1fr) — Methodological sections**
   * `<h1>` `Research & Provenance` (the page H1, in the context strip —
     not repeated here). The left column starts with `<h2>` `Methodology`.
   * Four `<h3>` sub-sections, one per phase:
     - `Phase 3 — Feature engineering` (2-sentence summary; references
       `docs/feature_space_manifest.md`)
     - `Phase 4 — Model fitting` (references `docs/phase4_contract.md`)
     - `Phase 5 — Analysis` (references `docs/phase5_figure_catalog.md`)
     - `Phase 6 — Synthesis` (references `docs/phase6_contract.md`)
   * Each sub-section has a figure-caption-style annotation in
     `--font-mono`, `--font-size-xs`, `--color-text-faint` giving the
     doc path.
   * Below: `<h2>` `Reproducibility` + a `<dl>` of verified facts
     (pipeline path, frozen test files, backend test count `445`,
     OpenAPI SHA-256).
2. **Right column (320px, sticky) — Artifact index + limitations**
   * `<h2>` `Artifact index` + a compact table (Caption: `Table 5. Frozen
     research artifacts.`) Columns: Path, SHA-256 (prefix). Rows from the
     recorded frozen-file list.
   * `<h2>` `Limitations` + a `<ul>` of honest limitations (no live
     dataset integration, no case API, etc.).
   * `<h2>` `Scientific cautions` + a `<ul>` of 2–3 cautions (anomaly ≠
     fraud; cross-domain comparison is unsound; results are
     manifest-verified, not live).

**Why this reflects A + C:** the editorial methodology sections are the
journal voice; the artifact index and cautions are the casebook
audit trail.

---

## 9. Desktop-minimum-width gate

When `window.innerWidth < 1280`, the workspace composition area is
replaced by a centered gate panel:

```
Desktop window required

PEIARS is an analytical workbench that requires a desktop-sized window.
Widen your browser window to at least 1280 CSS pixels, or use a desktop
monitor.

Current width: <N>px
```

* `--font-editorial` for the heading, `--font-interface` for the body.
* The identity bar, switcher, context strip, and provenance footer remain
  visible (the user is still authenticated and can navigate / log out).
* `role="alert"` so screen readers announce the gate.
* Re-evaluates on resize.

---

## 10. Self-critique against A + 2B + C (preview)

The final report will contain the full self-critique with screenshots.
Preview of the design intent:

* **A (editorial, 25%)** — Overview heading + Research methodology
  sections. **Succeeds if** the editorial voice reads as a journal.
  **Falls short if** the workflow map looks like a progress bar.
* **2B (workbench, 50%, dominant)** — Anomaly Analysis four-region grid;
  Data Observatory three-column; Cross-Domain matrix. **Succeeds if**
  the Analysis canvas visually dominates. **Falls short if** the
  deferred panels read as empty rather than as honest reservations.
* **C (casebook, 25%)** — Investigation three-column split; Research
  artifact index; provenance footer. **Succeeds if** the casebook
  structure is visible. **Falls short if** the case model `<dl>` reads
  as documentation rather than as a layout affordance.

The workbench is dominant: the Anomaly Analysis workspace is the largest
visual expression of the design philosophy. The previous sidebar
dashboard is gone.
