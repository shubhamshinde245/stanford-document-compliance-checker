---
name: stanford-ui
description: Audits and restyles the Stanford Document Compliance Checker frontend to the Stanford Cardinal dashboard system (Cardinal sidebar, sandstone canvas, high-radius floating cards, Source Sans 3 and Source Serif 4). Use when editing UI, CSS, Tailwind, layout, components, or pages, and when the user asks to audit the design, run stanford-ui, or fix visual drift.
---

# Stanford UI

Keep this app on the Stanford Cardinal dashboard system. Do not invent a second palette, typeface, or radius scale.

## Quick start

1. Read [design-tokens.md](design-tokens.md)
2. Scan frontend files (see scope below)
3. Fix every violation in place
4. Verify Checker and Policies in the browser before finishing

## Scope

- Explicit audit (“audit the design”, “run stanford-ui”, “fix visual drift”): scan all of `frontend/src/**/*.{tsx,css}`
- Ambient UI work: scan changed files plus `frontend/src/app/globals.css`

Do not restyle the FastAPI backend, PDFs, or docs.

## Audit checklist

- [ ] Tokens live in `@theme` (`canvas`, `paper`/`elevated`, `cardinal`, `sidebar-from`/`sidebar-to`, radii, `shadow-card`)
- [ ] Shell is a sandstone cradle: outer padding, solid Cardinal `#8C1515` sidebar, rounded main pane
- [ ] Sidebar stays fixed; only the main pane scrolls (`h-full overflow-hidden` on body/shell, `overflow-y-auto min-h-0` on main)
- [ ] Cards use `rounded-card` and `shadow-card`
- [ ] Buttons, inputs, selects, textareas, file drop use `rounded-control`
- [ ] Pass/warn/fail and “New”/“Updated” use `rounded-pill`
- [ ] Source Sans 3 for UI; Source Serif 4 for titles and big numbers
- [ ] No leftover hex (`#fffdf8`, `#f8e8e8`, `#c4b8a4`) in components — use theme colors
- [ ] No `rounded-sm` on cards, buttons, inputs, or sidebar chrome
- [ ] No navy, electric blue, Inter, Roboto, or Cardinal page-wash on `body`

## Forbidden

See the full list in [design-tokens.md](design-tokens.md). Never introduce a second design system.

## After fixes

Verify at `http://localhost:3000`:

1. Checker empty state, sample load, and results (score card + finding pills)
2. Policies: stats, category bars, filters, policy cards
3. Collapsed sidebar
4. A ~390px viewport

Behavior stays the same. Visual only unless a control is unusable.
