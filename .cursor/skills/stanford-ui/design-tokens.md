# Stanford Cardinal dashboard tokens

Canonical values live in `frontend/src/app/globals.css` `@theme`. Match these; do not invent new ones.

## Color

| Token | Hex | Role |
| --- | --- | --- |
| `canvas` / `sand` | `#f4efe6` | Page cradle behind sidebar + main |
| `paper` / `elevated` | `#fbf8f2` | Cards, inputs, main pane wash |
| `ink` | `#2e2d29` | Body text |
| `muted` | `#5e574e` | Secondary text |
| `line` | `#d9d1c3` | Borders |
| `cardinal` | `#8C1515` | Official Stanford Cardinal (PMS 201 C, RGB 140 21 21). Sidebar, actions, labels |
| `cardinal-dark` | `#820000` | Official Cardinal Dark — primary hover |
| `sidebar-from` / `sidebar-to` | `#8C1515` | Sidebar is solid `#8C1515`, not a fade |
| `pass` | `#175e54` | Palo Alto — success |
| `warn` | `#8c6a12` | Warning |
| `fail` | `#8c1515` | Failure (same as Cardinal) |

Toastify CSS variables may keep hex that duplicate these tokens. Components must not.

## Radius and shadow

| Token | Value | Use on |
| --- | --- | --- |
| `--radius-shell` | `1.75rem` | Sidebar and main pane |
| `--radius-card` | `1.25rem` | Cards, policy tiles, stat tiles |
| `--radius-control` | `0.9rem` | Buttons, inputs, drop zone, score well |
| `--radius-pill` | `999px` | Severity, New/Updated, category bars |
| `--shadow-card` | `0 18px 40px rgba(46, 45, 41, 0.08)` | Floating cards |

## Type

- **Sans:** Source Sans 3 (`--font-source-sans`) — labels, body, buttons, nav
- **Serif:** Source Serif 4 (`--font-source-serif`) — page titles, card titles, metric values
- Cardinal uppercase tracking labels (`0.14em`–`0.18em`) for section kicker text

## Layout

- `body`: `h-full overflow-hidden bg-canvas`, no Cardinal radial wash
- Shell: `flex h-full gap-3 overflow-hidden p-3`
- Sidebar: `h-full` fixed (does not scroll), solid official Cardinal `#8C1515` (`bg-[#8C1515]`), white text
- Active nav: `bg-white/15`; hover: `bg-white/10`
- Main: `min-h-0 flex-1 overflow-y-auto rounded-shell bg-paper/55`
- No dummy search, command palette, or avatar chrome

## Component recipes

**Card**

```
rounded-card border border-line/80 bg-paper shadow-card
```

**Primary button**

```
rounded-control bg-cardinal text-paper hover:bg-cardinal-dark
```

**Secondary button**

```
rounded-control border border-line bg-transparent hover:border-ink
```

**Control (input / select / textarea)**

```
rounded-control border border-line bg-paper focus:outline-cardinal
```

**Sidebar collapsed mark:** white tile, serif “S”, Cardinal text, slightly arched (`rounded-t-[1.15rem] rounded-b-[0.4rem]`).

## Forbidden

- Navy, electric blue, purple, or a dark maroon fade on the sidebar (stay on `#8C1515`)
- `rounded-sm` (or sharper) on cards, buttons, inputs, sidebar nav
- Hardcoded `#fffdf8`, `#f8e8e8`, `#c4b8a4` in TSX
- Inter, Roboto, system-ui-only stacks (Source Sans/Serif must remain)
- Cardinal as a full-page background instead of the sidebar
- Fake dashboard chrome (⌘K search, notification bell, user avatar)
