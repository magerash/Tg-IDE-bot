# TG-IDE-Bot — Compact Layout Handoff

Design reference: `Bot Panel Compact.dc.html` (this project). Drop-in file: `handoff/panel-compact.html` — full page (Warm Mono style) with the compact layout and all JS wired.

## Layout changes vs current panel

1. **Keys & Actions moved to side rails.** Desktop structure:
   ```
   .main-row (flex, gap 12px, align-items:flex-start)
   ├─ .rail  Keys   — flex:0 0 var(--rail-w); position:sticky; top:12px
   ├─ .center       — flex:1 1 480px; min-width:0; column of panels
   └─ .rail  Actions — same as Keys rail
   ```
   Rails are `position:sticky` so Keys/Actions stay beside the type/shell zone while scrolling. Keys rail is a 2-col grid; Actions rail is a stacked column.

2. **Fluid width → inputs scale horizontally.** `.wrap{max-width:1500px}` (was 900px). Every input: `flex:1 1 auto; min-width:0` inside `.input-row{display:flex}` — stretches with the window at any size.

3. **Compact Screen panel.** SCREEN label + Screenshot/Window/Auto/Click buttons on one row (`.screen-head`, label `margin-right:auto`). Capture area `min-height:var(--screen-h)`.

4. **Windows + Projects side by side** (`.wp-grid`, 2 cols → 1 col on mobile).

5. **Mobile (≤920px):** rails hidden; `#mob-tools` shows Keys and Actions as horizontally scrollable chip rows placed directly under Type Text. Chips are ≥44px tall (tap targets). At ≤560px: body padding 10px, screen buttons wrap.

## Single source of truth for buttons

Keys/Actions buttons are rendered by JS (`renderTools()`) from `KEYS` / `ACTIONS` arrays into every `[data-keys]` / `[data-actions]` container — desktop rails and mobile chip rows never drift apart. Add a key = add one array entry.

## Knobs (CSS vars on :root)

- `--rail-w: 170px` — rail width
- `--screen-h: 260px` — screenshot area min-height

## Tokens (Warm Mono)

bg `#faf9f7` · card `#fff` · text/accent `#1c1917` · dim `#a09b93` · border `#eae7e2` · accent-soft `#f0eeea` · ok `#16a34a` / `#e9f7ee` · err `#dc2626` / `#fdeceb` · radius: panel 14px, btn/input 9px · shadow `0 1px 2px rgba(28,25,23,.05)`

## Assumed API endpoints (verify against your bot)

Kept from original: `/api/status`, `/api/screen`, `/api/window`, `/api/key`, `/api/click`, `/api/type`, `/api/sh`, `/api/git`, `/api/build`, `/api/apks`.
Added for the new panels — **rename to match your backend**: `GET /api/windows`, `POST /api/focus {id}`, `GET /api/projects`, `POST /api/project {name}`, `POST /api/vscode {name}`, `POST /api/claude {prompt}`. "Click: ON" mode maps clicks on the screenshot to real coordinates via `naturalWidth/naturalHeight` and posts `/api/click`.

---

# Refine view (v0.19.0) — `handoff/refine-view.html`

Second Mini App surface: a text workbench with the Type section only — mic, AI cleanup, ✨ Improve,
Twin, markdown preview, Copy. No screen, no keys, no shell. Drop-in reference for `web/refine.html`,
the same way `panel-compact.html` was for `index.html`.

Open the mockup and use the top-right toggle to check both palettes; the `:root` blocks are lifted
verbatim from `index.html`, and `test_refine_and_index_share_theme_tokens` fails if they drift.

## Layout
Single column, `max-width:640px`, **no media-query layout switching** — the dashboard's
rail/`display:contents` machinery is what makes its mobile layout fragile, and nothing here needs it.
Controls above the field (thumb reaches mic/Improve without scrolling past a tall textarea); Copy
below it (terminal action, and a mis-tap next to the mic must not cost a recording). At ≥760px with
markdown on, textarea and preview become a 2-column grid.

## Decisions and status
See the "Decisions & status" table rendered at the top of the mockup itself — it is the status board
for this view and is updated in place rather than duplicated here.

## Not in this view, on purpose
Type button, the 11 presets, image paste, Blocks toggle, quick-keys, screen/lightbox/scroll,
shell/Claude/git/build/restart, Windows/Projects/Scheduled/CC-metrics. Every one is a system endpoint
path; `test_refine_page_has_no_system_endpoints` enforces it. Text leaves this view via Copy only.

Full contract: `docs/chunks/features/refinement-view.md`.
