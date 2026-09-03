# Web Dashboard — Local HTTP Control Panel + Telegram Mini App

## Quick Reference
- Server: `aiohttp` on `WEB_PORT` (default 8080)
- Files: `handlers/web.py` + `handlers/web_extra.py` + `web/index.html` + `web/common.js`
  + `web/refine.html` + `utils/webauth.py` + `utils/vscode.py` (integrated-terminal focus)
- Auth: Telegram Mini App initData (HMAC) or Bearer token (`WEB_TOKEN`)
- Starts alongside Telegram bot if `WEB_TOKEN` or `WEBAPP_URL` set
- Mini App: `WEBAPP_URL` (HTTPS via Cloudflare Tunnel) → "Panel" menu button;
  `/panel` also carries 🖥 Dashboard + ✨ Refine `web_app` buttons
- **Two surfaces**: `/` = this dashboard (everything), `/refine` = text workbench only
  → [`refinement-view.md`](refinement-view.md)
- Start everything: **`start_bot.bat`** (tunnel keeper → bot loop); also in `shell:startup`
- Setup: `docs/documentation/miniapp-setup.md`, `start_tunnel.bat`

## Overview
Local web dashboard providing REST API + HTML UI for all bot commands. Runs concurrently with the Telegram bot on the same event loop. Token-based auth on all endpoints.

## Layout (compact, from `docs/design-system/handoff/`)
- Desktop: `[left rail] [fluid center column] [right rail]` — rails `position:sticky`,
  center fluid up to 1500px, inputs stretch (`flex:1 1 auto; min-width:0`)
- Each rail is a compact stacked column (`display:flex;flex-direction:column;gap:12px`):
  **left = Windows then Keys**, **right = Projects then Actions**. Tools panels tagged `.rail-tools`.
  Rails stay **compact** so `position:sticky;top:12px` **locks** them in view while the long center
  scrolls. (Tried bottom-aligning Windows/Projects to the Screen bottom via a big `margin-top` —
  it made rails ~screen-tall > viewport, breaking sticky lock; reverted. `alignRails()` now just
  clears any stale margin.) Rail recents (`#win-recent`/`#proj-recent`) stack as a full-width
  vertical list
- Center panel order: Screen → Type Text → History → Scheduled → mobile chips → Claude → Shell
- Keys/Actions buttons rendered by JS `renderTools()` from `KEYS`/`ACTIONS` arrays into all
  `[data-keys]`/`[data-actions]` containers — desktop rails + mobile chips share one source;
  add a button = add one array entry
- Screen panel: `Screen` title, then image, then capture controls (`.screen-head`: Screenshot/Window/Auto/interval/Click) **below** the image — closer to the Type input for fast tapping
- `KEYS` entries are `[label, key, repeat, fn?]`; `fn` overrides the default `doKey()`. `1` `2` `3` sit at the front of Keys and type digit+Enter via `doTypePreset` (answer numbered prompts)
- `Click 250,1000` removed from `ACTIONS` — the screenshot Click-mode (flexible x,y) replaces it; `doClick()` still used by click-on-image + click-refresh
- Windows panel (dropdown + Refresh/Focus + recents) lives in the **left rail under Keys**;
  Projects panel (dropdown + Refresh/Set/VSCode + recents) in the **right rail under Actions** —
  they align with the rails, NOT inside the Screen section. Screen is a plain full-width panel
- Mobile ≤920px: `.rail,.center{display:contents}` flatten all panels into one `.main-row` column
  (`flex-direction:column;align-items:stretch`), then explicit order sets a mobile-specific flow
  (deliberately *not* the desktop layout): `#screen-panel` (-4) → `#win-panel` (-3) → `#proj-panel` (-2)
  → `#type-panel` (-1) → DOM order (Keys chips → History → Scheduled → Actions chips → Claude → Shell).
  Rationale: Screen first (the thing you look at), Windows right under it (switched constantly),
  Projects next; Type Text follows so screenshot→input stays one scroll flick.
  `.rail-tools` hidden (mob-tools chips cover them). Guarded by `test_mobile_order_and_accordion`
- **Accordion panels**: Windows + Projects carry `.acc` — tapping the `<h3>` title toggles
  `.collapsed` (`togglePanel(id)`), which hides everything but the title
  (`.panel.acc.collapsed>:not(h3){display:none}`) and flips the ▾/▸ caret (CSS `::after`).
  State persists per panel in localStorage (`acc_win-panel` / `acc_proj-panel`) and is restored
  on load. Collapse is CSS-only — selects/recents keep updating underneath, so expanding shows
  current data with no refetch. Works on desktop rails too, matters on mobile
- Knobs: `--rail-w` (rail width), `--screen-h` (screenshot min-height) on `:root`
- Kept from pre-redesign: lightbox zoom viewer, rect-based click mapping, macOS color guard,
  hardened `api()`, `/api/folders`+`{folder}`+`{title}` contracts (handoff's `/api/projects`,
  `{id}`, `/api/vscode` were renamed to match backend)
- Action status field (`[data-status]`, in Actions rail + mobile chips panel): every `toast()`
  also writes into it via `setStatus()` — last action result + timestamp stays visible
- "Restart Bot" action: confirm → POST `/api/restart` → poll `/api/status` every 2s (60s cap)
  → "Bot online" + reload dropdowns. Server re-execs itself: `os.execv(python, bot.py)`
- Single-instance guard (`utils/singleton.py`, called in `bot.py:main`): kills other
  `bot.py` python processes before binding. Required — os.execv detaches from
  start_bot.bat, whose loop then spawns a second instance → port 10048 crash loop.
  **Kills via psutil API calls, never taskkill/powershell subprocesses** (guarded by
  `test_singleton_guard_spawns_no_processes`): on 2026-08-19 process creation on the
  box hung system-wide, every subprocess kill timed out (taskkill 10s, WMI powershell
  20s) and a zombie held :8080 through a 40-min crash loop, while an API-level kill of
  the same pid worked instantly. `p.wait(5)` after kill — the port frees only when the
  process is really gone
- Type/Claude/Shell = textareas (`bindSendKeys`): Enter sends, Shift+Enter new row
  (multiline OK — `_type_text` pastes via clipboard); all resize:vertical, terminal too
- Paste compose (`attachments[]` + `#attach-row` chips): image paste / Alt+V → thumbnail
  chip; text > 400 chars or > 8 lines → block chip "N rows · M chars". Send on Type:
  images → `/api/paste` (CF_DIB + Ctrl+V) then text blocks + typed text → `/api/type`.
  Small text pastes natively.
- Image paste = **file-path typing** (target is Claude Code in a VS Code terminal; a terminal
  cannot receive a Ctrl+V image). `/api/paste` saves the PNG to `%TEMP%/tgbot_paste/img_<ms>.png`
  and types its path (quoted if it has spaces) + trailing space into the focused window via
  `_type_text`; Claude Code attaches the file. `doType` types each image path, waits
  `IMG_INGEST_MS` (700ms), then types the user text + Enter. (`utils/clipimg.py`
  `set_clipboard_image` kept but unused — clipboard-image paste never worked into a terminal.)
- `bindSendKeys`: keydown Enter (no Shift, not composing) → send; Shift+Enter falls through to the
  default newline. `enterkeyhint="send"` set. (A `beforeinput`/`insertLineBreak` mobile fallback was
  tried and reverted — it also caught Shift+Enter's line break and broke multi-row input.)
- History panel (`tg_history` localStorage, cap 100): records type/shell/claude/image
  sends; click row → refill matching input; Clear button; per-device
- Auto-refresh interval: `#auto-int` select (1/2/3/5/10s), persisted `tg_auto_int`,
  live-restarts running timer. ALL refreshes (auto, after-click, lightbox) go through
  `refreshCurrent()` — follows `lastCapture` mode; never hardcode `doScreen` in a refresh
  path or window mode silently flips to full screen
- Lightbox controls: `#lb-controls` (top-right corner) holds **`#lb-close` only**; the
  view pills split by what they act on: layout `#lb-lay` + Auto ON/OFF (green when on)
  in `#lb-view-row`, the right zone; the seconds pill `#lb-int` (1/2/3/5/10s, shared with
  main `#auto-int`) at the right end of the **left** zone; Click (red when on) leads the
  **centre** key row, immediately left of the arrows — it is tapped mid-gesture, so it
  belongs with the keys, not with the refresh controls.
  Lightbox auto timer refreshes zoomed image in place; stopped on close.
  Fresh frames are pushed into the open lightbox from `capture()`'s `onload`
  (with `onload=null` so zoom/pan transform survives) — `_lbRefresh()` just triggers
  `refreshCurrent()`. Do NOT read `#screen-area img` right after `await refreshCurrent()`:
  `capture()` resolves before its `onload` swaps the new node in, so you'd copy the
  previous frame (that was the "zoomed view lags one interval" bug)
- Mode buttons `#btn-screen`/`#btn-window` highlight active `lastCapture` via
  `_syncModeButtons()` (called in capture onload); main Auto/Click buttons toggle
  `.btn-ok` (green) / `.btn-red` (red) while active
- Click-refresh: `await doClick()` BEFORE scheduling refresh (unawaited click + timer =
  refresh captures pre-click state over slow tunnel → "one click lag"), then double
  refresh at 500ms + 1600ms — second pass catches slow UI updates
- Capture race guard: `_capSeq` generation counter — every `capture()` bumps it, stale
  results dropped at each await point (after api, in onload). `_capBusy` flag makes auto
  ticks skip while a capture is in flight (no pile-up at 1s interval). Without this,
  an older capture finishing late overwrites a newer one (stale image / mode flip-back)
- Screenshot flicker-free + STALE-CLOSURE GUARD: capture() builds fresh `Image()`, onload
  does `im.onload=null` + `area.replaceChildren(im)`. NEVER swap via `oldImg.src = ...` —
  the old element's stale onload re-fires and overwrites `lastRect`/`lastCapture` with the
  previous capture's values → clicks map to wrong coordinates (bug fixed 2026-07-21)
- White flash on every refresh (fixed 2026-08-30): `load` fires when the bytes arrive,
  NOT when the bitmap is decoded. `replaceChildren(im)` with an undecoded `<img>` paints
  one frame with the old image already gone and the new one not yet paintable, so
  `#screen-area`'s own background shows through. onload is `async` and awaits
  `im.decode()` (try/catch — `onerror` owns real failures) BEFORE the swap; the seq guard
  is re-checked after the await, since a newer capture can land during the decode.
  `#screen-area` background/border also moved to `var(--card)`/`var(--border)` — it was
  hardcoded `#fafbfc`, i.e. a white box in the dark theme. Locked by
  `test_frame_swap_waits_for_decode`
- `doAuth()` must not assign TOKEN before validating input non-empty (empty wipes session)

## Typing target (v0.21.0) — where the text actually goes

`POST /api/type` takes an optional `window` title. It is raised **inside the same
request** as the paste, then `TYPE_FOCUS_SETTLE` (0.6s), then type. A separate
`/api/focus` call would leave a gap, and a gap is enough: measured 2026-08-31,
`focus_window_exact('✳ Claude Code')` returned `ok=True` and 700ms later the
foreground was `Claude` — Claude Desktop takes focus on its own, and every browser
message then landed in it while the bot answered `Typed:`.

The reply always carries `window` + `proc` (what really received the text) and,
when a target was asked for, `focus` / `focus_msg` / `on_target`. A mismatch is a
red toast naming both windows — a message eaten by the wrong app must never look
like one that arrived.

Dashboard: **Target** button in the Type controls row (`tg_type_target`).
`active` = old behaviour, foreground wins. On = the window chosen in the Windows
panel, its name on the button, green when armed, red when armed with nothing
picked. `renderTarget()` is called from `loadWindows()` and the select's
`onchange`, so the label never names a window that is no longer selected.

### The editor trap — why a raised VS Code window still ate messages

Measured 2026-08-31, after the target fix shipped and the bot was restarted:

```
09:25:27  Typing 17 chars into 'Tg-IDE-bot - Visual Studio Code' [code.exe] via ctrl+shift+v   200 OK
09:25:58  Typing 19 chars into 'Tg-IDE-bot - Visual Studio Code' [code.exe] via ctrl+shift+v   200 OK
```

Neither arrived. Right window, right key, right clipboard — wrong **control**: the
caret sat in the editor, where `ctrl+shift+v` is `markdown.showPreview`, not paste.

So `terminal` on `/api/type` is **auto-ON when the key is absent**; only an explicit
`false` opts out (`/api/paste` does). `focus_terminal_if_active()` is a no-op unless
VS Code is really foreground, so a plain terminal or a GUI app pays nothing. The
dashboard additionally sends `terminal: true` whenever the chosen Target matches
`/visual studio code/i` — a terminal window has no inner control to miss, VS Code
does. Nothing in this product ever wants text pasted into a source file.

## Keyboard layout pill (v0.21.0) — `GET/POST /api/layout`

Shows the layout of the **foreground window** and switches it on tap. `utils/layout.py`.

Not decoration: what lands in a remote terminal is whatever the target window's
layout produces. From a phone that is invisible — you send a command, Cyrillic
arrives, and you learn about it from the next screenshot. It is also the fastest
check for the class of bug in `phase2-screen-input.md` ("The keyboard layout ate
every keystroke").

- Read and write both target `GetForegroundWindow()`. The layout is **per window**
  in Windows; `ActivateKeyboardLayout` would change the bot's own thread and
  nothing the operator can see.
- Switch = `WM_INPUTLANGCHANGEREQUEST` posted to that window, not a faked
  Alt+Shift: the shortcut is user-configurable and often off, the message is what
  Windows itself posts.
- The result is **verified** by re-reading the layout for up to 0.5s. `PostMessage`
  cannot fail loudly, and a window that ignores it would leave the pill lying.
- `POST` with no `lang` cycles to the next installed layout — one tap. The reply
  carries the new state, so no follow-up GET (which could already show a third
  value).
- UI: `#lay-btn` in the bottom quick-keys bar, `#lb-lay` in the zoomed viewer,
  fixed `min-width` so an RU→EN switch cannot reflow the key row under a thumb.
- **No timer.** Refreshed on load, on `visibilitychange`, after a focus, after
  every `/api/key`, and after text is sent — the moments the answer can have
  changed. A background poll through the reverse-SSH tunnel is exactly what
  v0.16.3/v0.16.4 were about.

## Config (`config.py` / `.env`)
| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_PORT` | 8080 | HTTP port |
| `WEB_TOKEN` | (empty) | Auth token — dashboard disabled if empty |
| `WEB_SCREEN_MAX_W` | 1920 | Fallback frame width when the client sends none (`0` = native). The dashboard's Fit/1280/1920/Full selector overrides it per request |
| `WEB_SCREEN_QUALITY` | 70 | Fallback JPEG quality (clamped 20–95) |

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/frame` | **Live-view transport** — `{mode, max_w, quality, fmt, hash}` in; raw WebP/JPEG bytes out (`X-Rect`/`X-Hash`/`X-Mode` headers), `204` if unchanged |
| POST | `/api/screen` | Legacy base64 JSON full screenshot — `{max_w, quality, hash}` in, `{image, hash, rect}` or `{same:true}` out |
| POST | `/api/window` | Legacy base64 JSON window capture (same body/reply shape) |
| POST | `/api/key` | Key press `{key, repeat}` |
| POST | `/api/type` | Type text `{text, enter, terminal, new_terminal}` — `terminal:true` moves the caret into the VS Code integrated terminal first (`utils/vscode.focus_terminal_if_active`), `new_terminal:true` opens a fresh one instead of reusing the active terminal; reports `{terminal, terminal_msg}`, and a non-VS-Code foreground still types but says so |
| POST | `/api/click` | Mouse click `{x, y}` |
| POST | `/api/scroll` | Wheel scroll `{dir: up\|down, notches, x?, y?}` → `utils/mouse.scroll_at` |
| POST | `/api/sh` | Shell command `{cmd, timeout}` |
| POST | `/api/git` | Git command `{args}` |
| GET | `/api/status` | Version, uptime, OS |
| POST | `/api/build` | Gradle build `{apk, cwd}` |
| GET | `/api/apks` | List APKs `?filter=` |
| GET | `/api/windows` | Open window titles (web_extra) |
| POST | `/api/focus` | Focus window `{title}` — exact match (web_extra) |
| GET | `/api/folders` | PROJECTS_ROOT subfolders (web_extra) |
| POST | `/api/code` | Open folder in VSCode `{folder}` — validated against list (web_extra) |
| POST | `/api/claude` | `claude -p` `{prompt}`, 300s timeout (web_extra) |
| GET/POST | `/api/project` | Current project / switch `{folder}` (web_extra) |
| POST | `/api/restart` | Restart bot process (`os.execv` after 0.7s reply flush) |
| POST | `/api/paste` | `{image: b64, paste: bool}` — image → PC clipboard (CF_DIB, `utils/clipimg.py`) + Ctrl+V (web_extra) |
| POST | `/api/improve` | `{text, style, twin}` → `{improved, twin_used, twin_missing}` — AI rewrite of Type-field text, never auto-sends; 502 on LLM failure (web_extra). See [improve-text.md](improve-text.md) |
| GET | `/` | Dashboard HTML page |
| GET | `/favicon.ico` | Rounded-square TG-blue icon (`#229ED9`, big white "TG", rx 110/512), no auth (browsers request it unprompted). Assets in `web/` (`favicon.svg` source of truth, PNGs/ICO regenerated via Pillow script — supersample 4× → LANCZOS). Linked in `<head>` via `/static/…`; guarded by `test_favicon_assets_and_links` |

## The VPN trap (v0.16.4) — check this FIRST when the phone is slow
`bot.magerash.com` resolves to **the same VPS that hosts the user's VPN**. With
the VPN on, the phone tunnels bot traffic *to the VPS through the VPS*:

```
phone →AmneziaWG UDP 36698→ VPS → amn0 bridge → Caddy:8443
     → ssh reverse tunnel → PC → all the way back, wrapped in WireGuard
```

The **PC is immune**: WireGuard always excludes its own endpoint IP from the
tunnel (`Find-NetRoute 213.165.40.182` → `Ethernet`, not the AmneziaVPN adapter).
Android WireGuard protects only its own UDP socket, so *application* traffic to
the endpoint IP still goes into the tunnel. That asymmetry is the whole bug.

**Fix: split-tunnel the bot's host/IP on the phone.** No privacy is lost — the
destination *is* the VPN server, so the carrier already sees that IP either way.
Amnezia excludes by **address**, not hostname, so the list has to be re-checked
after every VPS migration — current address `213.165.40.182` (was
`45.150.33.106`, filtered by RF DPI 2026-08-07; retired from DNS and from the
VPS's own outbound path on 2026-08-24, release in Aeza still pending).

### "The dashboard won't load" — check the transport before the tunnel (2026-08-24)

Caddy advertises HTTP/3, and once a browser has seen that `alt-svc` header it uses
**UDP/443 and does not fall back to TCP** when that path degrades. The page hangs while
the server is perfectly healthy. This cost five hours before the access log showed
**207 of 207 requests from that machine arrived over HTTP/3** — a box that is "down"
does not log 207 requests from the client reporting it.

The ten-second discriminator, because this looks exactly like the 2026-08-07 address
filtering:

```bash
curl -sS -o /dev/null -w 'h1 %{http_code}
' --http1.1 https://bot.magerash.com:8443/
curl -sS -o /dev/null -w 'h3 %{http_code}
' --http3   https://bot.magerash.com:8443/
```

**Filtering kills `curl` too; QUIC does not.** So if `curl` works and only the browser is
stuck, stop looking at the VPS — disable QUIC in the browser
(`chrome://flags` → Experimental QUIC protocol → Disabled). The `alt-svc` header carries
`ma=2592000`, so a Chromium browser stays off TCP for **thirty days** after its first
visit — which is why this reappears long after the visit that caused it.

Full writeup: `docs/imported/vps-architecture.md` (gitignored) → *Key facts / gotchas*, the
"a site can time out in the browser while `curl` gets a clean answer" bullet. That file is
now an **exact copy** of the canonical one at
`C:/Projects/Pryatki/docs/infra/vps-architecture.md` (v1.10) — sync it by replacing the
file, never by editing both.

What was ruled out, and how (repeat these before suspecting code):

| Suspect | Test | Result |
|---------|------|--------|
| Server | `bot.window rect` → access-log delta | 40ms/frame |
| PC→VPS link | `head -c 10000000 /dev/zero \| ssh vps "cat >/dev/null"` | 46 Mbit/s |
| VPS shaping | `tc qdisc show` | none |
| Hairpin/DNS/NAT | `docker exec amnezia-awg2 wget https://bot.magerash.com:8443/` | serves the page |
| MTU black hole | client MTU 1420→1280 | **no change**; `awg0` is a correct 1420 |

Signature that says *policing*, not MTU or size: frames start at 2–3s and decay
to 17–18s **within one session** while `/api/click` stays instant. A size cliff
would be constant; a draining token bucket looks exactly like this.

Gotcha met twice here: `pkill -f <pattern>` and `ps | grep <pattern>` match the
very command that contains the pattern — `pkill -9 -f watch8443` killed its own
ssh session (exit 255). Use `grep "[w]atch"` or a split literal.

## Frame transport (v0.16.3) — `POST /api/frame`
The live view uses **one binary endpoint**, not the JSON ones (those remain only
so cached older clients keep working).

Request: `{mode: 'screen'|'window', max_w, quality, fmt: 'webp'|'jpeg', hash}`
Response: raw image bytes; `X-Rect` (l,t,w,h), `X-Hash`, `X-Mode` headers;
**`204` with no body** when `hash` matches what the client already shows.

Why binary+WebP, measured through the tunnel at 1280px:

| Transport | Bytes |
|-----------|-------|
| base64 JPEG (`/api/window`) | 109KB |
| binary JPEG | ~83KB |
| **binary WebP** (`/api/frame`) | **50KB** |

base64 inflates by 33%; WebP is ~37% smaller than JPEG at equal quality
(`method=2` — the Pillow default 4 triples encode time for ~2% more shrink).
Net effect: **1920px now costs 82KB, less than the old 1280px did** — the
resolution went up while the bytes went down. Client feature-detects WebP via a
canvas `toDataURL` probe and falls back to JPEG.

Frames arrive as `Blob` → `URL.createObjectURL`; the previous object URL is
revoked on swap (`_objUrl`) or the webview leaks a frame every tick.

**Adaptive sizing** (`_adapt`, `Fit` mode only): median round trip over the last
4 frames; > 90% of the Auto interval → shrink 25% (floor 480px); < 35% → grow
back toward view width. Explicit 1280/1920/Full are never auto-changed.

**Auto pauses while `document.hidden`** — the loop keeps scheduling but skips the
capture, and `visibilitychange` resumes with an immediate frame. A dashboard left
open in a background tab was pulling 1.2GB/day through the tunnel (2026-08-03),
competing with the phone for the same single-TCP ssh transport.

### Diagnosing "the live view is slow" (do this before changing code)
`bot.log` access lines carry the **User-Agent**, so each client is separable:
```python
# Telegram webview vs desktop: cadence and bytes per client per day
'Telegram-Android' in ua and 'Chrome' in ua   → phone Mini App webview
'Telegram-Android' in ua (no Chrome)          → Telegram app itself
```
Compare the *median gap* between `/api/frame` (or `/api/window`) completions per
client. Server processing shows up as the gap between the `bot.window: Active
window rect` debug line and the access line — it has been ~40ms throughout, so a
large client-side gap is always the link, never the capture.

2026-08 baseline: desktop 3.0s median / 3.0s p90 (interval-bound, healthy);
phone 7s median / 31s p90 (link-bound). July 23 the same phone ran 1.0s median.
Link checks that ruled the server out: `head -c 10000000 /dev/zero | ssh vps
"cat > /dev/null"` → 46 Mbit/s up; `tc qdisc show` on the VPS → no shaping.

## Client robustness (v0.16.2) — read this before touching `api()`
- **Every `fetch` needs a deadline.** `fetch()` has none. Through the tunnel, a
  request whose upstream ssh died hangs on the proxy indefinitely; with the
  single-flight queue below, one such request wedges `_capBusy` forever and the
  live view is dead until reload. `api(method, path, body, timeoutMs)` aborts at
  20s by default. Pass `0` only for jobs with a server-side timeout
  (`/api/sh`, `/api/claude`, `/api/build`, `/api/key` with `interval`×`repeat`).
  `CAP_STUCK_MS` (30s) resets the queue if a flight somehow outlives its abort.
- **Telegram's webview caches the Mini App per URL** and treats `no-cache` as
  advisory — a phone can run a month-old UI against a new bot, which looks
  exactly like "the bot is broken, but the browser works". Two defenses:
  `miniapp_url()` stamps `?v=VERSION` on the menu-button URL, and the page
  compares its own `CLIENT_VERSION` against `/api/status`, reloading once as
  `?v=<server>` on mismatch (sessionStorage guard stops reload loops).
  **`CLIENT_VERSION` in `index.html` must be bumped with `config.VERSION`** —
  `test_client_version_matches_config` enforces it.
- **Mini App initData expires after 24h** (`INIT_DATA_MAX_AGE`) → 401 on every
  call. Client renders "Session expired — close and reopen the Mini App".

## Transfer resolution (v0.16.2)
`#res-sel` in the Screen panel, persisted as `tg_screen_res`:

| Setting | max_w | quality | Frame @2048×1152 |
|---------|-------|---------|------------------|
| Fit | view width × DPR (≤1920) | 65 | ~35KB (phone ≈800px) |
| 1280 | 1280 | 68 | ~90KB |
| **1920** (default) | 1920 | 72 | ~180KB |
| Full | 0 = native | 80 | ~276KB |

Measured through the tunnel: 0.50–0.71s per frame across the whole range.
Lightbox forces ≥1920 regardless (and re-captures on open) — it exists to read
fine text. `max_w: 0` means *native*, so server-side parsing must not use `or`
defaulting on it (`_frame_opts`, regression-tested).

## Live view performance (v0.16.1)
The whole path is one reverse-SSH pipe, so frame bytes and the tiny `/api/click`
POST compete for it. Three rules keep clicks feeling instant:

1. **Single-flight capture queue** (`requestCapture()` in `index.html`) — one frame
   request in flight, ever. Anything asked for while busy collapses into one
   pending run. Auto ticks, post-click refreshes, lightbox refreshes and mode
   buttons all funnel through it.
2. **Auto = self-scheduling `setTimeout` chain**, not `setInterval` — the gap is
   measured from the previous frame's completion, so a slow link stretches the
   period instead of queueing ticks that can never be served.
3. **Only the pixels the view can show** — `_frameW()` = container width × DPR,
   capped at 1280 (1920 when the lightbox is open). Phone ≈ 800px ≈ 40KB/frame.

Plus `hash`: client echoes the last frame's md5, server replies `{same:true}`
(~80 bytes) when the screen is pixel-identical. Idle screen ≈ free.

Regression history: before this, a click fired blind refreshes at +500ms/+1600ms
on top of a `setInterval` tick, and an open lightbox ran a *second* refresh loop.
The queue grew without bound — clicks took ~15s to appear, and the `_capSeq`
guard dropped out-of-order results so sometimes the frame never updated at all.

Status line shows real cost per frame: `Screen updated · 430ms · 40KB`.
If ms > the Auto interval, that number *is* the refresh rate.

## Tunnel (production access path)
`start_tunnel_vps.ps1` — reverse SSH: PC:8080 → VPS:18080; Caddy on VPS serves
`https://bot.magerash.com:8443` → localhost:18080.

**Target is `root@vpn.magerash.com`, never a raw IP** (2026-08-09). The VPS address
changed once already — `45.150.33.106` was silently dropped by RF DPI and
replaced by `213.165.40.182` — so the hostname is the stable layer and the next
migration is a DNS edit instead of a code edit. The A-record must stay
**DNS-only / grey cloud**: Cloudflare's proxy is HTTP-only and would kill ssh.
The raw IP survives only as a commented fallback for when DNS itself is broken.

ssh resolves once per connection attempt, so **a DNS change is picked up only by
a reconnect** — `taskkill /IM ssh.exe` and let the keeper dial again (the
watchdog does the same within 60s).

**One command starts everything:** `start_bot.bat` → launches the hidden tunnel
keeper (`start_tunnel_hidden.vbs` → `start_tunnel_vps.ps1`), then the bot in its
5s auto-restart loop. Safe to run twice.

**Single-instance keeper:** `start_tunnel_vps.ps1` exits immediately if another
powershell is already running it. Three launch paths exist (start_bot.bat,
scheduled task **TgBotTunnel**, bot watchdog) and two keepers means two ssh
clients fighting over remote port 18080 — the loser dies on
`ExitOnForwardFailure` and retries every 5s, so the tunnel flaps.
The guard must exclude `$PID`: this process's own command line matches the pattern.

Troubleshooting "web app broken":
1. `502 Bad Gateway` on public URL = Caddy alive, SSH tunnel DOWN (bot itself likely fine)
2. Restart tunnel: `schtasks /run /tn TgBotTunnel` (or run `start_bot.bat`)
3. Local check bypassing tunnel: `http://127.0.0.1:8080/api/status` with Bearer token
4. Tunnel dies on console close/Ctrl+C (task exit code 0xC000013A) — check `Get-Process ssh` if 502
5. Flapping / random 15s stalls → count keepers:
   `Get-CimInstance Win32_Process -Filter "Name like 'powershell%'" | ? { $_.ProcessId -ne $PID -and $_.CommandLine -match 'tunnel_vps' }`

**Watchdog** (`utils/tunnel.py`): bot runs `tunnel_watchdog()` background loop when
`WEBAPP_URL` set — every 60s checks ssh.exe alive, else `schtasks /run /tn TgBotTunnel`,
falling back to `wscript start_tunnel_hidden.vbs` when the task isn't registered
(no longer self-disables). Tunnel self-heals as long as the bot runs.

## Autotests
`tests/test_web.py` — run `python -m pytest tests/ -q` (~0.5s, no bot token/network needed):
- API endpoints respond 200 + `ok:true`; unauthorized → JSON 401 (not HTML)
- `/api/project` switch + unknown-folder rejection (restores state after)
- `/` serves full HTML
- **HTML/JS consistency**: every `onclick` handler defined, every `getElementById` id exists,
  every `/api/...` path in JS registered on server — catches broken buttons without browser
- `_frame_reply()` hash short-circuit: same hash → `{same:true}` with no image, stale → full frame
- `_grab_to_jpeg(max_w=…)` actually downscales and shrinks the payload
- Quick-keys bar + viewer row carry Tab **and** Sh+Tab, tinted apart; freeform fields send on Enter
- Claude launcher present in Actions + viewer, brand orange in both palettes, asks for `terminal:true`
- `/api/type {terminal:true}` focuses the VS Code terminal **before** typing, skips (and reports)
  when the foreground window is not VS Code, and is unchanged without the flag
- The command-palette sequence exists in exactly one file (`utils/vscode.py`)
- All handler modules import
Run after ANY change to `web/index.html`, `handlers/web*.py`, or handler refactors.

Note: `/api/screen` and `/api/window` return `rect` (pyautogui coordinate space) for click mapping.
Circular-import guard: `web.py` imports `web_extra` inside `create_web_app()`; `web_extra` imports web helpers inside handlers.

## Shared client code (`web/common.js`)

Loaded by **both** `index.html` and `refine.html` as a plain `<script src>` at the end of `<body>`
(after the DOM — these blocks run `getElementById` at top level). No modules, no bundler, no build
step.

What lives there: `applyTheme`/`toggleTheme`, `_twa`/`TG` init, `CLIENT_VERSION` +
`_checkStaleClient`, `doAuth`, `api()`, `toast`/`setStatus`, `autoGrow`, History, the humanize and
twin toggles, `doImprove`, the whole markdown renderer, and `toggleMic`/`blobToWav`/`sttUpload`.

**THE RULE: anything that calls a system endpoint stays in `index.html`.** `common.js` may reach
only `/api/status`, `/api/stt`, `/api/improve`, `/api/scope`.
`test_refine_page_has_no_system_endpoints` scans the file for literal endpoint strings — including
inside comments, so do not name them there either. Dashboard-only helpers (`alignRails`,
`renderTools`, `bindScrollPads`, `requestCapture`, `openLightbox`, `_tgBack`) carry no `/api/`
string and are caught separately by `test_common_js_has_no_dashboard_only_code` — `alignRails` in
particular does `.observe(document.querySelector('.center'))` and would throw on any page without a
`.center`, killing every statement after it in the same script.

Why extraction and not a second copy: each of those blocks is scar tissue from a real bug (the WAV
re-encode, the markdown escape-before-inject, `api()`'s abort deadline, the loud humanize-failure
toast). Two copies means the next fix lands on one page and silently misses the other, with no test
able to force parity.

**Amended dependency rule.** "No CDN, no framework, no build step" stands. A same-origin
`/static/` file served by our own aiohttp is *not* a dependency: it travels the same reverse-SSH
tunnel as the HTML and is version-stamped with it.

**Version stamping is load-bearing.** Both pages hardcode
`<script src="/static/common.js?v=<VERSION>">`, pinned to `config.VERSION` by
`test_static_script_stamps_match_version`. The chain: stale HTML pins the *old* `?v=` and so loads
the *old* `common.js` — a consistent pair, not a mixed one — then `_checkStaleClient` reloads with
`?v=<server>`, which the webview cannot serve from cache, and the fresh HTML pulls the fresh JS.
Drop the stamp and you get fresh HTML against cached JS: silent, per-device, invisible on desktop.

**Per-page hooks** read by `common.js` at load, so they must be set in an inline `<script>`
*before* the `common.js` tag: `window.MD_STORAGE_KEY`, `window.MD_DEFAULT_ON`,
`window.HISTORY_TARGETS`, and `window.AUTH_HEADERS` (which credential every request carries —
without it `api()` prefers initData and the refine view's scoped token would be bypassed).

**Tests read both halves.** `_html()` in `tests/test_web.py` returns `index.html + common.js`
concatenated; reading `index.html` alone would let ~16 regex invariants pass by looking at less.
`tests/test_refine.py` mirrors the id and onclick checks against `refine.html + common.js`, because
the concat validates `common.js`'s `getElementById` calls against the dashboard only.

## Auth (`utils/webauth.py`)
- Mini App: header `X-Telegram-Init-Data` → `validate_init_data()` verifies HMAC
  (secret = HMAC_SHA256("WebAppData", BOT_TOKEN)), 24h max age, user id must equal
  `ALLOWED_USER_ID`. Automatic inside Telegram — no token entry.
- Browser: `Authorization: Bearer <WEB_TOKEN>` or `?token=` (localStorage).
  Empty `WEB_TOKEN` never matches (guard in `check_token`).
- `setup_menu_button(bot)` sets MenuButtonWebApp on startup when `WEBAPP_URL` set.
- **Scoped tokens**: `POST /api/scope {scope:"refine"}` (full auth required) mints a 12h
  `refine.<exp>.<hmac>` bearer. `_check_auth_refine()` accepts it and is called by exactly three
  handlers — `api_status`, `api_stt`, `api_improve`; the other 24 use plain `_check_auth` and
  reject it. Deliberately a second function, not a `refine_ok=` kwarg: a bad merge then fails
  *closed*. `test_every_api_handler_checks_auth` pins both the coverage and the count of 3.
  Details → [`refinement-view.md`](refinement-view.md).

## Dashboard UI (`web/index.html`)
- Light minimal "Warm Mono" theme (paper bg `#faf9f7`, black primary buttons); variants A/B/C
  explored in Claude Design project `5e47f664-755f-4de1-b40d-55777a59d983` (`docs/design-system/README.md`)
- Panels: Screen, Keys, Actions, Windows (focus), Projects (VSCode), Type text, Claude, Shell
- Auto-refresh screenshots (3s interval)
- **Click-on-image**: "Click: ON" toggle → click fraction of displayed img × capture `rect` →
  `/api/click`, auto re-capture after 700ms (handles resolution scaling)
- **Lightbox**: "Click: OFF" (default) → click screenshot opens fullscreen viewer — wheel/pinch
  zoom (0.8×–12× fit), drag pan, double-tap 3×, Esc/backdrop close; pointer-events, `touch-action:none`
- **Lightbox click mode**: own "Click: OFF/ON" toggle (top-right, next to ×) — tap on zoomed
  image inverts pan/zoom transform → natural px → capture `rect` → `/api/click`; auto re-capture
  after 700ms updates lightbox image keeping zoom/pan. Resets to OFF on each open. Toast z-index 300
  (above lightbox).
- Terminal output for shell/git/build/claude commands
- Keyboard shortcut: backtick focuses shell input
- **Quick-keys bar** (`#quick-keys`, fixed viewport bottom, z-90 — under lightbox z-200 and
  auth overlay z-100): … (layout) / **↑ / ↓** / ← / → / Enter / **Sh+Tab** / **Tab** /
  **Claude** / freeform field, for answering Claude Code question prompts from anywhere on
  the page. ↑/↓ lead the arrow cluster because Claude Code moves its option **selector**
  vertically — ←/→ alone cannot pick an option, which is what the bar exists for. Left side shows a
  recently-tapped trail (`_qkPush`, cap 8, newest last, RTL-ellipsis so the newest stays
  visible; "no keys tapped yet" empty state) — fed centrally from `doKey` **and** from
  `qkSend`/`doClaudeCode`, so Keys-rail and mob-chip presses appear too. Body gets
  62px bottom clearance at every breakpoint; toast raised to `bottom:64px`.
  A near-identical row lives **inside the lightbox** (`#lb-keys`, bottom-centre, z-201,
  white-pill style) — deliberately WITHOUT ↑/↓: the viewer row is already the widest thing
  over the picture. `test_quick_keys_bar_has_vertical_arrows` pins that as a decision, not
  a forgotten place. Guarded by `test_quick_keys_bar_at_bottom`
- **The bar folds (v0.21.0).** `#qk-toggle` — a 26px caret button at the far left, the
  one slot the phone block already empties (`.qk-trail{display:none}`): screen edge,
  thumb-natural, nothing else there to mis-hit. Same idiom as `.panel.acc` and the
  same `acc_` namespace (`acc_quick-keys`), caret from a **pseudo-element**
  (`▾` open / `▴` folded), never markup. Collapsed is a ~24px sliver, not a
  disappearance — the handle stays at the exact pixel the thumb just left, so the way
  back is where the way out was. **Default expanded**: shipping a hidden-by-default
  control in the release that fixes "I can't see the arrows" would manufacture the
  same bug one control over.
- **The clearance follows the fold via a `<body>` class, not a custom property.**
  `body.qk-hidden{padding-bottom:26px}` + `body.qk-hidden #toast{bottom:28px}`.
  A `--qk-h` variable would mean rewriting both `62px` literals into `var()` — and 62
  is the *expanded* height in two places `test_quick_keys_bar_at_bottom` pins
  byte-for-byte. `body.qk-hidden` is `(0,1,1)` against `body`'s `(0,0,1)` and media
  queries add no specificity, so **one rule overrides both breakpoints**. The class
  goes on `<body>` rather than the bar because the two things that must follow the
  fold — body's clearance and `#toast` — are not descendants of it. ~36px returned.
- **Phone compaction rule, and it is a rule, not a pile of numbers: horizontal is the
  scarce axis.** Every overflowing row on this page scrolls or wraps sideways, never
  down — so at ≤560px *inline* padding and gaps shrink (`.panel` 14→11, `.tight`
  12→9, `.btn` inline 14→10, `.btn-sm` 11→8, chips 12→9, gaps 6→5) and the **tappable
  height of every control is held**: no vertical padding below 6px, `#mic-btn` keeps
  46px, and the scroll pads *grow*. `test_quick_keys_bar_has_vertical_arrows` fails on
  any two-value padding in that block with a vertical under 6px.
- **`#qk-type` is a sibling of `.qk-btns`, not its last child.** It was inside, so at
  ≤560px it scrolled away with the keys — the exact opposite of what the comment
  beside that rule claimed for two versions. Fixed and pinned by a test. When editing
  `.qk-btns` in the phone block, **edit the existing rule in place**: the guard does
  `re.search(r"\.qk-btns\{([^}]*)\}")` and first match wins, so a second rule would be
  invisible to it.
- Known gap, recorded not fixed: `env(safe-area-inset-bottom)` is unhandled, so on a
  notched iPhone the bar sits under the home indicator. The reported device is Android.
- **On a phone the keys scroll, they never wrap.** The bar already overflowed 360px before
  ↑/↓ (`.qk-btns{flex-shrink:0}` + no overflow = the field was silently pushed off-screen).
  At ≤560px the trail and the Claude launcher hide (they have homes elsewhere), the four
  arrows square off (`.qk-arrow{min-width:30px;padding:6px 0}`) and `.qk-btns` becomes
  `overflow-x:auto` with the scrollbar hidden — the keys pan under the thumb while the
  field stays pinned right. Wrapping is banned: the 62px clearance is a fixed number, so a
  second line would sit on top of the last panel
- **Tab is its own key, not a variant of Sh+Tab.** Sh+Tab cycles Claude Code's mode; Tab
  advances/accepts, which is what the Tab-then-Enter answer flow needs — a bar carrying only
  Sh+Tab cannot do it. They are one keystroke apart, so they are tinted apart: Sh+Tab keeps
  the green (`btn-ok-soft` on the page, `.lb-ok` pill in the viewer), Tab is plain
- **Freeform field replaces the fixed `1`/`2` buttons** (`#qk-type` in the bar, `#lb-type` in
  the viewer, `.qk-input`): `qkSend(id)` → `doTypePreset(text)` = text + Enter, field cleared,
  trail gets a 12-char excerpt + ⏎. Typing "1" still answers a numbered prompt, and "3"/"yes"/a
  path now work too — the two buttons could only ever answer two of them. `qkDigit()` is gone;
  the Keys rail keeps its 1/2/3 for one-tap replies
- **Claude launcher** (`ACTIONS` entry + `#lb-claude` in the viewer, `.btn-claude` = brand
  orange `--claude` `#d97757`/dark `#e08a6b`): types `claude` + Enter with `terminal:true`, i.e.
  starts a Claude Code session in the VS Code integrated terminal without touching the keyboard.
  Sends `new_terminal:true`, i.e. **Terminal: Create New Terminal**, not "Focus on Terminal View":
  measured live 2026-08-25 — focusing the last active terminal, which already ran Claude Code,
  made `claude` a *chat message to that session* instead of a launch. A new terminal is always a
  shell prompt and also covers a just-opened window with no terminal at all; `NEW_TERMINAL_WAIT`
  (1.6s, env `VSCODE_NEW_TERMINAL_WAIT`) lets the shell print its prompt, since keystrokes sent
  into that gap are dropped by the pty and read as "the button did nothing".
  Solid orange on purpose — it is the one button in Actions that starts a session rather than
  reporting on one. A missed terminal focus is a **loud** toast (`Typed "claude", but active
  window is not VS Code (…)`), never a cheerful "Typed:". Guarded by
  `test_claude_launcher_is_orange_in_both_surfaces`
- **Viewer bottom bar has three zones** (`#lb-bottom`, `left:14px;right:14px`,
  `justify-content:space-between`, z-201): `#lb-proj-row` left (project flow),
  `#lb-keys` centre — Click + ← → Enter Sh+Tab Tab + `#lb-type` (`flex:1 1 auto`, and
  the field itself is `flex:1 1 260px`, so the slack the bar has left lands in the one
  control that holds a sentence rather than a word) — `#lb-view-row` right (layout /
  Auto). Only
  `#lb-close` stays pinned to the top-right corner — it must not move as the rows
  reflow. On a phone each zone takes a full row (`flex:1 1 100%`) and keeps its own
  alignment; three zones side by side do not fit 360px. The left zone is the one
  left and centre zones both `flex-wrap:wrap` there — 2 selects + 4 pills, and 6 pills +
  the field, do not fit one 360px line; `#lightbox` is `overflow:hidden`, so an
  overflowing row does not scroll, it loses its last button off-screen (this is exactly
  how Click disappeared once). The field takes a full row of its own
  (`flex:1 1 100%`) — a share of the key row leaves it ~40px. Guarded by
  `test_viewer_controls_sit_in_three_zones`
- **Viewer left zone** (`#lb-proj-row`, z-201) — TWO selects, in this order:
  `#lb-win` (live `/api/windows` list, filled by the same `loadWindows()` that fills
  `#win-select`) + 🖥 Focus → `doFocusWin('lb-win')` focuses that title directly; then
  `#lb-proj` (folders) + Open + Claude + Click. Focus targets a **window**, Open/Claude
  need a **project** — one select cannot serve both, which is why there are two. Legacy
  `doFocusProj(selId)` (project → `'<folder> - Visual Studio Code'`) still serves the
  dashboard Projects panel: project
  `<select>` (filled by the same `loadFolders()` that fills `#proj-select`) + 🖥 Focus + Open +
  Claude. Whole "get a session running" flow — pick project → focus or open its window → start
  Claude Code — without leaving the zoomed screenshot. `doFocusProj` focuses
  `'<folder> - Visual Studio Code'`, matched server-side by containment so it still hits the
  window after VS Code prefixes the open file to the title; `doCodeSel('lb-proj')` opens a new
  window via `/api/code`. `_selectedProject(selId)`/`doCodeSel(selId)` take the select id, so
  the dashboard panel and the viewer share one code path
- **Viewer rows are compact on a phone** (`@media(max-width:620px),(max-height:520px)`): the
  rows float **over** the picture, so every pixel they take is screenshot lost. Desktop sizing
  (38px pills, 8px gaps) wrapped each row in two on a 360px phone — four rows covering half the
  view. Small screens get 32px pills, 6px gaps, `flex-wrap:nowrap`, and buttons pinned at
  `flex:0 0 auto` while the `<select>` and the freeform field absorb the leftover width
  (`flex:1 1 auto;min-width:0` — without `min-width:0` a flex item refuses to shrink below its
  content and the row overflows the viewport instead). 🖥 Focus drops its label
  (`.lb-lbl{display:none}`), the icon carries it. Also applies in short landscape windows, where
  height is the scarce axis. Guarded by `test_viewer_controls_stay_compact_on_a_phone`
- **Gesture guard now covers form controls**: `_lbCtl(el)` exempts `BUTTON`/`INPUT`/`SELECT`/
  `OPTION` from the viewer's pointerdown/up handling. Button-only (pre-v0.20) would have made a
  tap on the new field start a pan and dismiss the viewer mid-typing. `#lightbox` also sets
  `user-select:none;touch-action:none`, which the field/select take back locally
- **Markdown preview** (`#md-preview` pane under the Type field, `MD: ON/OFF` toggle):
  textareas can't render, so a read-only pane shows the field's markdown like a file view —
  headers/tables/fenced code/lists/blockquotes/links via `_mdRender()` in **`web/common.js`**
  (self-contained renderer, no CDN). Two XSS guards, both test-pinned: `_mdEsc` escapes
  `& < > " '` **before** any tag is injected (quotes matter — the link rule writes the URL into an
  `href="…"`), and `_mdSafeUrl` allows only `http(s)://`, `mailto:` and relative targets, so a
  `[x](javascript:…)` link renders as plain text instead of a one-click script execution. Auto-turns-on when Improve returns markdown-looking text (`_mdAuto`/`_looksLikeMd`) until
  the user toggles manually; the key is `window.MD_STORAGE_KEY` (`tg_md` here, `tg_md_refine` on
  `/refine`, which defaults ON). Re-renders on input and after every *programmatic* `.value` write —
  the `input` event does not fire for those, so transcription and history-refill call `_mdAuto`
  explicitly. Raw text is still what gets typed
- **Blocks toggle** (`Blocks: ON/OFF`, `tg_blocks`): ON = current behavior, paste >400 chars /
  >8 lines folds into a block chip; OFF = every paste lands inline in the field.
  Guarded with MD preview by `test_md_preview_and_blocks_toggle`
- **Improve text** (second `.type-controls` row): Twin toggle (`tg_twin`) · style select
  (`tg_imp_style`: structured/detailed/concise/→EN) · ✨ Improve → `POST /api/improve`,
  result replaces the Type field, never auto-sends; original saved to History as `draft`
  kind first. Details: [improve-text.md](improve-text.md)

### v0.13.0 additions
- **Entry defaults**: after login auto-capture starts + Auto 3s ON; `lastCapture` default `'window'` (Window mode); Click OFF
- **Double-click**: `/api/click {double:true}` → `pyautogui.doubleClick`; tap-delay 280ms pattern (`_imgTapTimer`, `_lbTapClick`) — 1 tap = single (after pause), 2 taps = double; works in main-screen Click mode + lightbox Click mode; zoom via pinch/wheel stays
- **Lightbox**: inherits main Auto state on open (`openLightbox` → `lbToggleAuto`); double-tap zoom cancels backdrop close timer (`_lb.closeTimer`) — was closing viewer
- **Windows/Projects**: header shows current focused window (`/api/windows` → `active`); top-6 recent chips (`bumpRecent`/`renderRecents`, localStorage `tg_recent_win/proj`, frequency-sorted) — one-tap focus/switch. The chip matching the active window / current project renders light green (`btn-ok-soft`) via `_activeWin`/`_curProj`; active window is also preselected in its dropdown

### Recents validation (v0.16.5) — why chips can't go stale
Recents live in localStorage and outlive the windows they point at, so a chip for
a closed window used to look tappable and do nothing. Rules now:

1. **Filter at render, never at write.** `renderRecents()` drops chips whose
   target isn't in the live list (`_winList` / `_projList`). Storage is untouched,
   so closing and reopening a window brings its chip back with its frequency.
2. **`_matchesLive()` must mirror `focus_window_exact()`** (`utils/window.py`):
   exact → containment either way → first-25-chars prefix. VS Code retitles per
   open file, so a chip saved as `Tg-IDE-bot - Visual Studio Code` has to match a
   live `index.html - Tg-IDE-bot - Visual Studio Code`. Exact-only matching would
   hide chips that focus perfectly well.
   `test_recent_validation_mirrors_server_matching` fails if either side drifts.
3. **Empty live list disables filtering** — a failed `/api/windows` must not blank
   the recents.
4. **`/api/focus` returns `gone`** (server-side `msg.startswith("Window gone")`).
   A failed focus retires the chip only when the window is really gone; "found but
   activation blocked (admin window?)" keeps it.
5. `RECENT_MAX_AGE` (30 days) drops unused entries on write, so a once-popular
   window that no longer exists can't hold a top-8 slot forever.

Projects match exactly (folder names from `PROJECTS_ROOT`), not fuzzily.

### Scroll arrows on the live view (`utils/mouse.py`, `POST /api/scroll`)
RustDesk-style ▲/▼ pair floating on the **right edge** of the screen view, and the
same pair in the lightbox (`#lb-scroll`). Tap = 3 notches, **hold = keep
scrolling**, release → one fresh frame.

**Contrast is a feature of this control, not decoration (v0.21.0).** Reported as
"I don't see arrows up and down there" on a phone — and they were rendering the
whole time. Ruled out first: no `@media` block touches `.scroll-pad` /
`.screen-wrap` / `#screen-area`, no JS sets `display` on the pad, it is not clipped
(the `overflow:hidden` is on `#screen-area` and the pad is its *sibling*), and the
device was proven **not** stale — the access log shows it calling `/api/layout`, an
endpoint that only exists in the current client. What was left was the styling:
`rgba(20,19,17,.42)`, no border, no shadow, a 15px glyph in a 40px circle, and
`:hover` — which **never fires on touch** — as the only rule that raised the
contrast. A dark pill on a dark editor screenshot reads as nothing at all.
- **Every colour in `.scroll-pad button` is a literal, never a theme var.** These
  float over the *screenshot*, so the page theme tells you nothing about whether the
  pixels behind them are a black terminal or a white document. Keying the fill to
  the theme optimises against the wrong variable.
- **The ring is the fix**, not the fill: `border:1px solid rgba(255,255,255,.55)` is
  what carries a dark pill over a dark editor, while the now-`.78` fill and
  `box-shadow:0 2px 8px rgba(0,0,0,.45)` carry it over a white document. Both, always.
- Glyph 15px → **17px/600** — ▲▼ at 15px inside a 40px disc is a speck.
- **`:active`/`.on` is `var(--ok)`, NOT `var(--accent)`.** In night theme `--accent`
  is `#ece9e4` while `color` stays `#fff`, so the held state of a hold-to-scroll was
  white on white — the one control whose whole interaction is "press and keep
  pressing" had no feedback at all in dark mode. `--ok` is what `btn-ok` and
  `#lb-auto.on` already mean by "this is running".
- At ≤560px the pads **grow** — 44px, gap 8→10, edge 10→8 — while everything else on
  the page shrinks. 40px is a mouse target; these are thumb-worked hold-to-repeat
  controls, and two 44px discs 8px apart are one mis-tap from scrolling the wrong way.
- **`#lb-scroll`/`#lb-zoom` deliberately do NOT join the ≤620px 38→32 compaction** —
  they only take the 8px edge alignment. That rule exists because *rows* of pills ate
  the picture; a two-button column on the extreme edge costs almost nothing, and
  shrinking the control this fix exists to make findable is the wrong direction.
  Written down so a later "unify the viewer pill sizes" pass does not quietly undo it.
- Guarded by `test_scroll_arrows_wired_in_ui`, which now pins the ring, the shadow,
  the 44px touch size and the absence of `var(--accent)` in the held state.

Two Windows facts the implementation exists for — both silently no-op if broken:
- `mouse_event(MOUSEEVENTF_WHEEL, …)` **ignores the x/y it is handed** unless
  MOUSEEVENTF_MOVE is set, and Windows routes the wheel by *cursor position*. So
  `scroll_at()` really moves the cursor over the target, scrolls, then puts the
  cursor back where the user left it (`SETTLE` 30ms first, so the message is out
  of the queue). Passing coordinates to `pyautogui.scroll(x=, y=)` does nothing.
- `dwData` counts **raw wheel units**, one notch = `WHEEL_DELTA` (120), and
  PyAutoGUI passes `clicks` straight through — `pyautogui.scroll(3)` is 3/120 of
  a notch, i.e. no movement at all. Notches are multiplied by 120.

Client rules:
- Buttons live in `.screen-wrap`, **not** inside `#screen-area` — `capture()`
  calls `area.replaceChildren(im)` on every frame and would wipe them.
- `_scrollPoint()` sends the centre of the frame on screen **only in Window
  mode**; in full-screen mode that point is just some spot on the desktop and
  whatever window sits there would eat the wheel, so it sends nothing and the
  server aims at the active window instead (`get_active_window_rect`).
- Hold-repeat is a chain measured from each request's **completion**
  (`_scrollHold` + `SCROLL_REPEAT_MS`), never `setInterval` — the tunnel carries
  one request at a time and a fixed interval piles them up exactly like the
  v0.16.1 capture bug.
- `pointerdown` on an arrow calls `stopPropagation()` so the lightbox pan handler
  never sees it; `pointerleave`/`pointercancel` stop the hold.
- `MAX_NOTCHES` (30) caps a single call, so a stuck hold can't fling a page.

### Zoom pad in the viewer (`#lb-zoom`)
`+` / `−` column on the **left edge** of the lightbox, mirroring `#lb-scroll` on the
right and sharing its `.scroll-pad` pill styling — the two read as one scheme.
- **Purely client-side**: `_zoomOnce(dir)` → `_lbZoomAt(innerWidth/2, innerHeight/2, …)`,
  the same helper wheel and pinch use, with the same `min*0.8 … min*12` clamp. No
  endpoint, nothing to keep the tunnel busy.
- Anchored on the **viewport centre** (the eye is there); wheel anchors on the cursor
  and pinch on the fingers, which is why the anchor is a parameter and not baked in.
- Hold-repeat is a plain `setInterval` (`ZOOM_REPEAT_MS` 110), which is safe *here*
  precisely because there is no request — the scroll pad must chain from completion.
- `closeLightbox()` clears the timer: a hold ended by the Telegram back button never
  sends `pointerup`, and the interval would go on zooming a hidden image.
- `pointerdown` does `preventDefault` + `stopPropagation`, so a zoom hold never turns
  into a pan (`_lbCtl` already exempts `BUTTON`, this is the second belt).
- Guarded by `test_zoom_pad_mirrors_the_scroll_pad`.
- **Esc closes the viewer** (document `keydown`, scoped to `display === 'block'`, with
  `preventDefault` + `stopPropagation`). Unhandled it went to the browser/webview —
  leaving fullscreen, dismissing a picker — while the overlay stayed put. On the
  dashboard Esc is left alone.

### Attachments
Images take the path-typing route (`/api/paste`), and so does every other file —
📎 in the Type panel / viewer, drag & drop, or a document sent to the bot in chat.
Details, limits and the rules that must not be undone: **`file-attach.md`**.

### Three ways the live view looked broken (all fixed, don't undo)
1. **Auto stopped for good after one bad frame.** `_autoSchedule()` is a self-scheduling
   chain; a rejected `requestCapture()` threw out of the timeout callback, so the next
   `_autoSchedule()` never ran. The button stayed green and nothing refreshed again.
   The reschedule now lives in a `finally`. A tick skipped because `document.hidden`
   also *says so* (`Auto paused — view hidden`) — a silent skip is indistinguishable
   from a dead loop, and some webviews report hidden while the operator is watching.
2. **The resolution selector did nothing while the viewer was open.** `_frameOpts()`
   promoted any choice below 1920 to 1920 whenever the lightbox was up. Only `Fit` is
   promoted now (a panel-sized thumbnail is not worth zooming into); an explicit
   1280/1920/Full is an instruction and is sent as chosen.
3. **Focus in the viewer looked dead.** `loadWindows()` re-runs after every focus and
   `_fillSelect` re-selected the *active* window, wiping the operator's pick — the next
   tap then focused the window already in front. `_fillSelect(..., sticky)` keeps a pick
   that is still on the list; window selects pass `sticky`, project selects do **not**
   (there `selected` is the server's current project, which is real state). `openLightbox`
   also refreshes the list, since windows change constantly.

### Window identity = tail key (v0.16.7) — why the current window went missing
Reported: focus a window, and its chip is often absent from the quick-pick list
and never turns green. Title is not identity — **VS Code puts the open file
first**: `config.py - Tg-IDE-bot - Visual Studio Code` vs
`index.html - Tg-IDE-bot - Visual Studio Code` share no prefix and neither
contains the other, so the v0.16.5 rules called the chip dead.

- **`tail_key()` / `_tailKey()`** — last two `" - "` segments lowercased
  (`tg-ide-bot - visual studio code`). Added as a 4th rule on both sides:
  `utils/window.py:focus_window_exact` (so an old-title chip still focuses) and
  `_sameWin()` in the dashboard. `''` for single-segment titles — must never match.
- **Two matchers, deliberately different strengths.** `_sameWin` (exact →
  containment → 25-prefix → tail) answers "will focus find it?" and mirrors the
  server. `_sameWinId` (exact → tail only) answers "is this the same window?" and
  drives merging, dedupe and the green highlight — containment is too loose there
  ("Telegram" is inside "Telegram Web - Google Chrome"; merging would lose a chip).
- **Highlight** compares with `_sameWinId`, not `===`, so a chip stored under an
  older title still lights up as current.
- **One window, one entry.** `bumpRecent` merges an existing entry with the same
  `_sameWinId` into the new title (counts summed). Before this, a retitling VS Code
  wrote one entry per open file and filled all 8 slots by itself.
- **Ordering ties break by recency** (`_recentOrder`: `n` desc, then `t` desc).
  Frequency-only order meant a fresh entry (`n=1`) lost to eight older `n=1`
  entries and the window just picked never showed.
- **Current window is pinned first** in `renderRecents()` and exempt from the
  top-6 cut — it may have been focused outside the dashboard and never bumped.
  Its live title is used, which is also the title that focuses reliably.

Tests: `test_tail_key_identifies_a_retitling_window`,
`test_current_window_chip_is_pinned_and_highlighted`,
`test_recent_validation_mirrors_server_matching` (now asserts the tail rule on
both sides).

### Lightbox self-close on Android (v0.16.7) — why panning killed the viewer
Zooming into a screenshot on the phone and dragging around closed the viewer (and
sometimes the whole Mini App) with no back press. Two independent causes:

1. **Telegram's vertical-swipe close.** A vertical drag inside a Mini App is the
   native "dismiss" gesture — panning a zoomed image is exactly that drag. Fixed
   at startup with `_twa.disableVerticalSwipes()` (Bot API 7.7+, wrapped in
   try/catch for older clients). `expand()` alone does not stop it.
2. **Pointer capture retargets pointerup.** `box.setPointerCapture()` makes every
   later pointer event report `target === #lightbox`, so `pointerup`'s test
   `e.target.id === 'lightbox'` was true even for taps that started on the image →
   backdrop-close timer fired. The decision now comes from **pointerdown**
   (`_lb.onBackdrop`), which is the only event with a truthful target.

Supporting guards, all in the same pointer block:
- `_lb.multi` — set once a second finger lands; a pinch tail can never be read as
  a close tap (`if (_lb.moved || _lb.multi) return`).
- `if (_lb.ptrs.size) return` — don't judge a tap while other fingers are down.
- `pointercancel` handler — a gesture stolen by the OS (system swipe, call, app
  switch) never sends pointerup; without it the finger stayed in `_lb.ptrs` and
  pan/pinch wedged (`ptrs.size` stuck at 2). Marks the gesture as moved.
- `openLightbox()` resets `ptrs/moved/multi/onBackdrop/lastTap` + clears the close
  timer; `closeLightbox()` clears them again.
- **Telegram BackButton** (`_tgBack`) is shown while the viewer is open, so
  hardware back closes the viewer instead of the Mini App.

`test_lightbox_survives_pan_gestures` locks all of it, including "pointerup must
not read `e.target.id === 'lightbox'` again".
- **Type controls row** (above input): AI: ON/OFF toggle (monochrome, `_syncHumanBtn`) left, big record button (46px, `#mic-btn` flex:1) center, Type right (88px sides)
- **Auto-grow**: all three textareas grow to content on input/mic-insert/history-refill (84→400px), shrink after send; visible diagonal grip via `::-webkit-resizer`
- `client_max_size=30MB` in `create_web_app` — default 1MB killed long WAV uploads

## Integration in `bot.py`
```python
async def run():
    # Start Telegram bot
    tg_app = _build_tg_app()
    await tg_app.initialize() / start() / updater.start_polling()
    
    # Start web server (if WEB_TOKEN set)
    runner = web.AppRunner(create_web_app())
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", WEB_PORT).start()
    
    await asyncio.Event().wait()  # run forever
```

## Related
- `handlers/panel.py` — Telegram inline keyboard (same commands)
- `config.py` — `WEB_PORT`, `WEB_TOKEN`
- See: `phase5-reliability-polish.md`, `panel.md`
