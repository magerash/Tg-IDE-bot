# Interactive remote control — architecture study

**Row 18 · 2026-09-08 · research only. No production code was written.**

**Supersedes [vnc-mode-research.md](vnc-mode-research.md)** (row 10) as the answer to *what to
build*. That pack stays as the record of what was **measured** on this machine; its numbers are
cited here rather than re-derived, and its Route A shipped as v0.22.0.

Labels used throughout: **Measured** = a number read off this machine, with the date and the
command; **Read** = read out of this repository; **Cited** = an external primary source with a
URL; **Observed** = a user report; **Estimate** = engineering judgement, marked as such.

---

# 1. Executive conclusion

**The recommended architecture is the one the project already has**, and the useful output of
this study is the argument for *not* changing it, plus the two things that are actually
missing.

- **Pure Bot (variant A) is impossible for the core UX.** A Telegram bot can never learn where
  a user tapped on a photo — no update type carries coordinates. This is not a limitation to
  work around; it removes the variant.
- **An external web remote-desktop stack (variant C) is more moving parts, not fewer — counted:
  5 today, 9 with noVNC, 11–12 with Guacamole**, and *neither removes any of the five*. The
  bot's other handlers — git, shell, scheduler, upload, the Claude launcher — have no VNC
  equivalent, so variant C is a second parallel system bolted beside the first. It would buy
  RFB's incremental updates and CopyRect, which solve a bandwidth problem that exists at
  20–60 fps and not at 0.5–2.
- **The Mini App (variant B) is already built and already carries the whole contract**: pointer
  coordinates, a canvas-free `<img>` with rect-mapped clicks, gestures, keys, auth by
  `initData`, all through the existing reverse-SSH tunnel on one process and one port.

So the MVP is not an architecture. It is **two verbs and one measurement**:

| # | Gap | State |
|---|---|---|
| 1 | **Direct typing** — the phone's keyboard straight through, no field, no Enter | not built; the operator's actual ask; row 17 |
| 2 | **Tile-diff frame transport** | measured to win 8–10×, but only *needed* if the phone's link is still slow; row 13 |
| 3 | **E1** — re-measure the phone's real throughput | one hour, decides whether #2 is feasibility or polish |

**Main risks.** Direct typing rested on an unverified fact — whether Claude Code inside Windows
Terminal accepts a synthesized `WM_CHAR` at typing speed. **Experiment E2 answered it on
2026-09-09: yes, byte-exact at 52 cps** (§18), so the risk that could have killed row 17 is
closed and the remaining ones are all on the client. And every gesture claim in this project has
been green in the test suite while broken on the device — `D-023` is the standing reminder.
Nothing here is finished until a line appears in `bot.log`.

---

# 2. Current project architecture

Only the parts that bear on remote control. Every row was read from the code today.

| Question | Answer | Where |
|---|---|---|
| Language / runtime | Python **3.14.3**, no virtualenv, user-wide packages | [environment.md](../environment.md) |
| Telegram framework | `python-telegram-bot` v20, **long polling** (`run_polling`, `timeout=10`) | `bot.py:99` |
| Entry point | one process, one asyncio loop: PTB polling **plus** an aiohttp app on `:8080` | `bot.py:73–105` |
| HTTP layer | aiohttp, ~40 `/api/*` routes | `handlers/web.py`, `handlers/web_extra.py` |
| Web surfaces | `/` full dashboard, `/refine` text workbench | `web/index.html`, `web/refine.html` |
| Auth | Telegram Mini App `initData` HMAC **or** `Bearer WEB_TOKEN`; a scoped `refine.*` token reaches exactly 3 handlers | `utils/webauth.py`, `D-010` |
| Users / roles | **one** — `ALLOWED_USER_ID`. No role model, no multi-tenant anything | `utils/auth.py` |
| Screen capture | `mss` → Pillow → JPEG/WebP; downscale, quality, hash dedup | `handlers/screen.py:_grab_frame` |
| Mouse | **all of it** through `utils/mouse.py`: `click_at` (button, double), `drag`, `scroll_at` | `D-018`, `D-019` |
| Keyboard | virtual-key codes via `keybd_event`, layout-proof; clipboard paste for text | `handlers/input.py:press_keys`, `_type_text` |
| Clipboard | Win32 `OpenClipboard`/`SetClipboardData`, 64-bit safe | `handlers/input.py:_set_clipboard` |
| Remote-control mechanism | **none external** — no VNC, no RDP, no SSH into the target. The bot *is* on the target | — |
| OS support | **Windows only, by design** — `pygetwindow`, the Win32 focus chain, the clipboard calls have no portable equivalent | [AGENTS.md](../../AGENTS.md) |
| Transport to the phone | reverse SSH tunnel → VPS → Caddy → HTTPS | `utils/tunnel.py`, `D-003` |
| Persistence | **JSON files** — `scheduled_messages.json`. No DB, no ORM, no migrations | `utils/scheduler.py` |
| Redis / queues / workers | **absent**. One `asyncio.create_task` scheduler loop | `bot.py:73` |
| WebSocket | **absent** — every live path is a chained POST (`D-011`) | — |
| Docker / systemd / service | **absent** — `start_bot.bat` + a Startup shortcut | [environment.md](../environment.md) |
| CI | **absent** — `pytest` locally, 103 tests, plus two wiki checkers gated by a hook | [verification.md](../../.claude/rules/verification.md) |
| Logging | stdlib to `bot.log` at DEBUG — **3.2 GB, unrotated** (row 3) | `config.py` |
| Reconnect | tunnel watchdog; client-side chained refresh with a stale-client version check | `bot.py:85`, `common.js` |

**The architectural fact that decides everything below:** the bot runs **on the machine it
controls**. There is no remote host, no network hop to the target, no protocol between the
controller and the desktop — only Win32 calls in-process. Every "remote desktop" architecture
in the landscape exists to solve a problem this project does not have.

---

# 3. Reuse opportunities

| Existing component | Reuse | Required changes | Notes |
|---|---|---|---|
| `POST /api/frame` | **as is** | none for MVP; tile-diff is row 13 | binary WebP, hash dedup, `X-Rect` header |
| `utils/mouse.py` | **as is** | none | already the single mouse path, with the settles `D-019` named |
| `handlers/input.py` `press_keys` | **as is** | none | VK codes — the *named-key* half of input, layout-proof |
| `handlers/input.py` `_type_text` | **keep, do not extend** | — | clipboard paste stays for long text; direct typing is a *second* path (`F-17` constraint) |
| `utils/webauth.py` | **as is** | none | `initData` HMAC is the session model; see §10 |
| `web/index.html` viewer | **as is** | add the typing surface | pointer machine, rect mapping, gestures all present |
| aiohttp app | **as is** | one new route for typing | no new server, no new port |
| `utils/vscode.py` | **as is** | none | terminal focus, single copy enforced by a test (`D-008`) |
| The tunnel | **as is** | none | already carries everything; a WebSocket upgrade passes (untested handshake) |

**Nothing needs replacing.** That is the finding, not a formality.

---

# 4. Feasibility matrix

| Feature | Pure Bot | Mini App | External Web UI | Verdict |
|---|---|---|---|---|
| Pixel-accurate click | **No** — no update type carries tap coordinates | **Ships** | Yes | Mini App |
| Right click | No | **Ships** — hold, or two-finger tap (`D-017`, `D-023`) | Yes | Mini App |
| Double click | No | **Ships** — one request, server-side (`GetDoubleClickTime`) | Yes | Mini App |
| Drag | No | **Ships** — one request, released in a `finally` (`D-018`) | Yes | Mini App |
| Scroll | Buttons only | **Ships** — wheel at a point (`utils/mouse.scroll_at`) | Yes | Mini App |
| Named keys / combos | Buttons | **Ships** — VK codes | Yes | either |
| **Typing, character by character** | No | **Missing** — needs `KEYEVENTF_UNICODE` | Yes | **row 17** |
| Screenshot refresh @2 s | Yes, `editMessageMedia` | **Ships** | Yes | Mini App |
| Partial-frame update | **No** — a photo is not a framebuffer | Possible (canvas) | Yes (RFB) | row 13 |

**Chat-surface verdict, stated once:** a bot can attach an inline keyboard (~8 buttons a row,
~100 per message, 64-byte payloads) or read reactions (admin-gated). That is **tens of zones
for two million pixels**. The chat can *show* a screen; it can never *be* a control surface.

---

# 5. Architecture alternatives

## A. Pure Telegram Bot

```
Telegram chat ──► photo + inline keyboard ──► callback_query ──► bot ──► Win32
```

**Verdict: removed by a documented fact, not by taste.** No Telegram update type carries the
coordinates of a tap on a photo — not `callback_query`, not `message_reaction`, not a reply.
The closest approximation is a button grid: ~8 per row, ~100 per message, 64-byte
`callback_data`. **Tens of zones for two million pixels.**
**Cited**: https://core.telegram.org/bots/api

| | |
|---|---|
| Complexity | lowest — no new surface at all |
| UX | a screen you can look at and poke with a coarse grid |
| Latency | `editMessageMedia` in place; a 0.5 Hz loop sits under the ~1 msg/s per-chat ceiling |
| Security | inherits the bot's allowlist; nothing new exposed |
| Changes here | small, and pointless: the Mini App already does more |

It survives as a **fallback surface**, not an architecture: `/screen` in the chat is useful when
the Mini App will not open. That is what the project already has.

## B. Telegram Bot + Mini App — *what exists today*

```
Telegram ──initData──► Mini App ──HTTPS──► Caddy ──► ssh tunnel ──► aiohttp :8080 ──► Win32
```

| | |
|---|---|
| Complexity | **zero new components** — one process, one port, one auth path |
| UX | real pointer coordinates, gestures, keys; the whole shipped dashboard |
| Latency | measured: ~133 ms control round trip, ~460 ms to new pixels (§9) |
| Security | `initData` HMAC or bearer; **no listening remote-control service anywhere** |
| Scalability | one operator by design; a second viewer is a dict key if row 13 lands |
| Changes here | one route + one client mode for direct typing |

The Mini App **is** a web remote-control UI. The question variant C really asks is whether a
*different* web UI, speaking a *standard protocol*, would be less work — and that is answerable
by counting.

## C. Telegram Bot + external Web Remote Desktop

```
Telegram ──► short-lived URL ──► browser (noVNC) ──WebSocket──► websockify ──TCP──►
VNC server (TightVNC/UltraVNC/TigerVNC) ──► Windows desktop
```

**What each piece actually is:**

- **noVNC** is only the browser half — an RFB client in JS. It cannot open a raw TCP socket, so
  it needs a VNC **server** *and* a WebSocket bridge. **Cited**: https://github.com/novnc/noVNC
- **websockify** is that bridge: a separate always-on process and port, which noVNC's own
  launcher downloads and runs. **Cited**: same. The bridge itself is not the hard part —
  ~40 lines of `aiohttp.web.WebSocketResponse` pumping bytes to `asyncio.open_connection`
  would fold it into the existing app (**Read**, inference) — but a real RFB **server** still
  has to exist on the PC, and today none does.
- **Apache Guacamole** is a different shape again: `guacd`, a C daemon that loads protocol
  support, plus a **Java web application requiring a servlet container, "usually Apache
  Tomcat"**. **Cited**: https://guacamole.apache.org/doc/gug/guacamole-architecture.html ·
  https://guacamole.apache.org/doc/gug/installing-guacamole.html
  And decisively for this project: **there is no supported native-Windows `guacd`** — the
  official path is a Linux build or the `guacamole/guacd` Docker image, so on this machine it
  means Docker Desktop or WSL2 underneath Tomcat and a JVM. **Read** (absence of a Windows path
  across the official install docs): https://guacamole.apache.org/doc/gug/guacamole-docker.html

**The VNC servers**, since one is mandatory for this variant:

| Server | License | Service | Auth |
|---|---|---|---|
| TightVNC 2.x | GPL; a separate commercial source licence (~€12k) only for embedding in closed software | yes, real Windows service | classic VNC-Auth |
| UltraVNC | GPLv3, Windows server only | yes | VNC-Auth **plus** MS-Logon I/II (Windows accounts) and MS-Logon III (X25519 + AES-256-GCM) |

**Cited**: https://www.tightvnc.com/licensing.php · https://uvnc.com/ ·
https://uvnc.com/docs/ultravnc-server/58-ultravnc-ms-logon-authentication.html

Classic VNC-Auth is the reason the auth column matters: the password is truncated to 8
characters and challenged with DES. UltraVNC's MS-Logon III is genuinely better — which is an
argument for *that server*, not for this variant.

Live friction is already documented at the junction this variant needs: a user reports being
unable to reach a **TigerVNC-for-Windows** server through Guacamole while other VNC clients
connect fine. **Observed**: https://github.com/TigerVNC/tigervnc/issues/1667

**The Python half, if this project were the RFB client** (read 2026-09-08):

| Library | Signals | Fit |
|---|---|---|
| `vncdotool` | 529★, 37 open issues, pushed today, PyPI 1.4.2 (2026-09-06); classifiers **3.10–3.13, no 3.14** | built on **Twisted** — an architecture mismatch with an asyncio/aiohttp process |
| `asyncvnc` | 44★, 12 open issues, last push **2024-04-26**, PyPI 1.3.0 (2023-02-26) | genuinely **asyncio-native** — the one point in its favour — and dormant |

**Cited**: https://github.com/sibson/vncdotool · https://github.com/barneygale/asyncvnc
No other maintained Python RFB client surfaced.

**What RFB would actually buy here.** `FramebufferUpdateRequest` carries an `incremental` flag,
so a client pulls only changed rectangles; `CopyRect` re-sends a scrolled region as a pointer
copy rather than pixels; `PointerEvent`/`KeyEvent` are first-class protocol messages.
**Cited**: https://www.rfc-editor.org/rfc/rfc6143.html

And then the honest reading against this project's operating point: **those optimisations buy
back bandwidth that matters at 20–60 fps.** At 0.5–2 fps a fresh full frame each tick is
already close to "send the whole rect", so ZRLE/TRLE and CopyRect solve a problem this project
does not have. The one genuine win is **standardised input framing** instead of ad-hoc
coordinate injection — and this project's injection layer is already written, tested and
scarred (`D-005`–`D-008`, `D-017`–`D-023`).

## The parts count

| | Parts |
|---|---|
| **Today** | 1 Python process (`bot.py` + aiohttp `:8080`) · reverse-SSH tunnel · Caddy · pyautogui/mss/pygetwindow **in-process** · the Mini App's own JS = **5**, built, debugged and documented |
| **+ noVNC** | a VNC server service · a WS↔TCP bridge · a new streaming load profile on the tunnel · a new client rendering path = **+4** |
| **+ Guacamole** | all of the above **plus** JVM + Tomcat + `guacamole.war` + `guacd` — which has no supported native-Windows build, so Docker Desktop or WSL2 becomes a prerequisite = **+6–7** |

**And the argument that ends it:** neither stack *removes* any of the five. The bot's other
`/api/*` handlers — git, shell, scheduler, file upload, the Claude launcher — have **no VNC
equivalent**, so variant C is a second parallel system bolted next to the first, not instead of
it. Nine moving parts to gain a bandwidth optimisation the operating point does not call for.

**One more thing it would break specifically here:** hop 3 asks the single reverse-SSH tunnel
to carry a **long-lived WebSocket stream** instead of the short chained requests it was built
for. That is precisely the load pattern `D-011` exists to warn about.

**Two gaps stated rather than filled.** TigerVNC's Windows service and localhost-binding
behaviour could not be established from available sources — its Windows server was dropped from
official maintenance in September 2020 and its own maintainers redirect users to
UltraVNC/TightVNC. And a widely-cited forum thread on Guacamole's Android typing could not be
fetched (403), so only its existence and title are confirmed.
**Cited**: https://github.com/TigerVNC/tigervnc · https://github.com/TigerVNC/tigervnc/issues/1213

---

# 6. Recommended architecture

```
Telegram  ──initData──►  Mini App  ──HTTPS POST──►  Caddy ──► reverse SSH tunnel
(phone)                  (index.html)                              │
                                                                   ▼
                                                        aiohttp :8080  (same process)
                                                                   │
                                    ┌──────────────────────────────┼───────────────┐
                                    ▼                              ▼               ▼
                            handlers/screen.py            utils/mouse.py    handlers/input.py
                            mss → Pillow → WebP           SendInput-class    VK codes · clipboard
                                    │                     click/drag/scroll   (+ unicode, row 17)
                                    ▼                              │               │
                                    └──────────────► Windows desktop ◄─────────────┘
```

**There is no remote-control protocol in this picture, and that is the point.** The controller
and the desktop are the same process on the same machine; the only network hop is the one
between the phone and that process, and it already exists, is already authenticated, and is
already the thing the whole dashboard runs on.

---

# 7. Input architecture

One model, already mostly implemented. `Ships` = today; `row 17` = the gap.

| Event | Path today | Notes |
|---|---|---|
| `pointer_move` | — | not sent; the cursor moves only as part of a click. Deliberate: a stream of moves is a stream of requests |
| `click` / `double_click` | `POST /api/click {x,y,double}` → `click_at` | double stays **one** request: Windows merges two down/up pairs only inside `GetDoubleClickTime` (500 ms), which two round trips cannot promise |
| `right_click` | same, `button:"right"` | fired by the hold timer at 350 ms, or a two-finger tap (`D-023`) |
| `drag` | `POST /api/drag {x,y,to_x,to_y}` | **one** request, press → interpolated moves → release in a `finally`. A button held *between* requests is one the tunnel can strand |
| `scroll` | `POST /api/scroll {dir,notches,x,y}` | cursor parked first — Windows routes the wheel by cursor position at injection |
| `key_down`/`key_up`/`hotkey` | `POST /api/key {key,repeat}` → `press_keys` | VK codes, so the active keyboard layout cannot mangle them |
| `text_input` (long) | `POST /api/type` → clipboard + paste hotkey | paste key chosen by target process (`D-006`, `D-007`); Enter sequenced once (`D-005`) |
| **`text_input` (live)** | **missing** | row 17 — see below |
| `clipboard` | `POST /api/paste` | image → file → path typed (a terminal cannot take a pasted image) |

## 7.1 Direct typing — the one real gap

**Server.** `SendInput` with `KEYEVENTF_UNICODE`: `wVk = 0`, the UTF-16 code unit in `wScan`.
Windows delivers `VK_PACKET`, `TranslateMessage` produces `WM_CHAR` with exactly that
character, and **`VkKeyScanW` is never consulted** — so the layout cannot mangle it, by
construction rather than by table lookup. This is the mechanism that makes the v0.21.0
Russian-layout bug class impossible.

**The constraint that shapes the design, on record since row 10:** a synthetic Ctrl does **not**
combine with a `KEYEVENTF_UNICODE` key. Character injection and hotkey injection are therefore
**two paths that never merge** — `press_keys` keeps every named key and combo, unicode gets
characters, and a helper taking "a string, possibly with modifiers" is the bug waiting to be
written.

**Client.** The naive design — listen to `keydown`, send the character — **cannot work on a
phone**, and this is normative rather than a bug. While a soft keyboard is composing, UI Events
requires `keyCode: 229` and `key: "Process"`/`"Unidentified"`; on Android essentially every
alphabetic key arrives that way. **Cited**: https://www.w3.org/TR/uievents/ ·
https://bugs.chromium.org/p/chromium/issues/detail?id=864911

What real terminals do instead, read from their source:

| Project | Strategy |
|---|---|
| **xterm.js** | hidden `<textarea>` + `CompositionHelper.ts`: `compositionstart` / `compositionupdate` / `compositionend`, and `keydown` only to *ignore* 229 |
| **ttyd** | reuses xterm.js unchanged — no separate mobile path |
| **noVNC** | persistent `<textarea>` with `autocapitalize/autocomplete/spellcheck` off, reading its value |
| **Guacamole** | a different strategy entirely: a "text input mode" that **diffs the field's value** against the previous one and infers the keystrokes |

The design that follows, for this project:

- **Primary signal is `beforeinput`**, switched on `inputType` — `insertText` and
  `insertLineBreak` carry the characters in `data`, `deleteContentBackward` means one
  backspace, `insertFromPaste` carries the pasted text. **Cited**:
  https://w3c.github.io/input-events/ · https://developer.mozilla.org/en-US/docs/Web/API/InputEvent/inputType
- **Do not forward during composition.** `insertCompositionText` is not cancelable and fires
  repeatedly; the committed result appears atomically at `compositionend`. Forward that block.
- **Backspace order**: `beforeinput`'s `deleteContentBackward` first, `keydown`+`Backspace` as
  fallback, and the sentinel-character trick (keep the buffer never-empty) only if a specific
  Android keyboard proves to misfire — CodeMirror carried that scar for years.
  **Read**: https://github.com/codemirror/codemirror5/issues/4934
- **Keyboard open/close is detected with `window.visualViewport` resize**, not Telegram's
  `viewportHeight` — a Telegram-iOS issue reports that field not reflecting the keyboard at
  all. **Observed**: https://github.com/TelegramMessenger/Telegram-iOS/issues/1296

## 7.2 Two honest limits this design cannot engineer away

**1. Per-keystroke typing is impossible during composition.** Whether a composed word arrives
character by character or as one block is IME- and browser-dependent and is not guaranteed by
any spec. For predictive Cyrillic input the reliable sync points are the *edges* —
`compositionstart` and `compositionend` — not the keystrokes between them. So "direct typing"
honestly means: **plain characters land immediately; a word the keyboard is predicting lands
when it is committed.** That is worth saying in the UI rather than discovering on the device.

**2. Autocorrect can rewrite text that has already been injected — and a keystroke cannot be
un-sent.** iOS Safari is documented to retroactively rewrite already-committed words, arriving
as `insertReplacementText`. Locally the editor just fixes itself; here the characters are
already inside a terminal on the PC. **Observed**:
https://github.com/facebook/lexical/issues/7614

The mitigation is to **defeat the suggestion layer**, not to handle the correction. xterm.js's
own maintainers propose the blunt version — make the hidden field `type="password"` inside a
`<form>` — precisely because Chrome-for-Android ignores `autocomplete`/`spellcheck` on a
`<textarea>` (noVNC hits the same wall). **Read**:
https://github.com/xtermjs/xterm.js/issues/2403 · https://github.com/novnc/noVNC/issues/357

That is the design decision this section exists to force: **the typing surface is a password
field, and autocorrect is off, on purpose.**

## 7.3 Batching — an engineering choice, not a cited practice

**No authoritative interval exists.** All four surveyed projects — xterm.js, ttyd, Guacamole,
noVNC — forward each committed input event immediately and let the transport absorb it; none
publishes a debounce window. Anything claiming otherwise would be invented.

But those four speak over a WebSocket to a local PTY, and this project speaks chained HTTPS
over a tunnel with a **measured ~133 ms warm round trip**. One request per character at a
typing speed of 5–8 cps is 5–8 concurrent-ish requests per second through a pipe `D-011`
exists to protect. So a small coalescing window is justified **by this transport**, and must be
labelled as such: an engineering choice, with the general perceptual bound (input lag becomes
noticeable above ~50 ms) as a ceiling rather than a target. **Start at 60–80 ms, measure, and
treat the number as tunable** (`TYPE_BATCH_MS`) rather than settled.

---

# 8. Screen pipeline

```
mss.grab  →  change detection  →  resize  →  encode  →  chained POST  →  <img> swap
 34 ms         15 ms (numpy)      BILINEAR   WebP m2     ~345 ms warm      decode-then-swap
```

**Measured 2026-09-08**, this machine, source 2048×1152 resized with LANCZOS:

| Resolution | JPEG q70 | WebP q70 m2 | PNG | 64-px tile diff |
|---|---|---|---|---|
| 1280×720 | 114.2 KB / 15.0 ms | **63.9 KB / 56.9 ms** | 370.0 KB / 16.5 ms | 6.6 ms |
| 1920×1080 | 218.8 KB / 3.4 ms | **115.5 KB / 53.2 ms** | 633.3 KB / 31.0 ms | 13.8 ms |
| 2560×1440 | 312.1 KB / 5.4 ms | **164.3 KB / 91.4 ms** | 954.0 KB / 52.2 ms | 24.8 ms |

- **WebP is right and PNG is not**: lossless is 3–6× the bytes at these sizes, and this
  transport is byte-bound, not CPU-bound. AVIF was ruled out at row 10 — its advantage is
  photographic and evaporates on flat UI, at several times the encode.
- **A finding this run added: the resampler is a bandwidth decision.** The same source at
  1280 px is **80.7 KB** with `BILINEAR` (row 10's table) and **114.2 KB** with `LANCZOS` — a
  ~40 % difference in payload for a sharper image. The code uses `BILINEAR`
  (`handlers/screen.py`), which is the right default for a thin link, and it should stay a
  deliberate choice rather than an accident.
- **The remote cursor is invisible, and nobody had written that down.** **Read**: `mss`'s
  Windows backend is one `BitBlt(... SRCCOPY | CAPTUREBLT)` and never calls `GetCursorInfo` or
  `DrawIconEx` — verified by reading the installed module. So **no frame this project has ever
  sent contained the mouse pointer.** It has not hurt yet because every interaction is
  absolute ("click *there*"), but it removes two options: a trackpad/relative-cursor mode
  (§14's most-cited UX finding) has nothing to render, and a drag gives no feedback about where
  the grab actually is. Drawing it is ~15 lines of `ctypes` at capture time and belongs with
  whichever of those lands first.
- **DPI scaling is untested and this machine cannot test it.** **Measured**: logical, physical
  and `pyautogui.size()` all read 2048×1152 here, i.e. scaling is 100 %, and the Python process
  reports `DPI_AWARENESS_UNAWARE`. On a display at 125 % or 150 % an unaware process is handed
  *virtualised* coordinates, so the captured frame and the injected click would disagree — the
  same class of silent mismatch as the multi-monitor gap. Nothing to fix today; a line in
  [environment.md](../environment.md) so the next person does not discover it live.
- **The 2-second model is wrong in one direction only.** Row 10 measured that **0 of 5**
  consecutive frames are byte-identical on a working desktop, so "skip if unchanged" never
  fires — while only **2.3 %** of tiles actually change. The refresh is not too fast; the
  *payload* is too whole.

---

# 9. Latency budget

**Measured** components are from row 10's appendix and today's table; **estimates** are marked.
The measured tunnel path is PC → internet → VPS → tunnel → PC, so the PC's uplink is counted
twice — it approximates the phone, it does not replace measuring it (**E1**).

| Stage | Latency | Main factor | Optimisation |
|---|---:|---|---|
| Pointer event → request sent | ~5 ms *(est.)* | JS handler | none needed |
| Request → server (warm) | **133 ms** | tunnel RTT | WebSocket saves the HTTP round trip, not the RTT |
| Injection: `click_at` | **~60 ms** | `MOUSE_MOVE_SETTLE` 40 + hold 20 | was ~200 ms before `D-019` |
| Injection: `drag` | ~340 ms | 12 interpolated moves + hold | fewer steps trades fidelity |
| Screen capture | **34 ms** | `mss` BitBlt | DXGI would not help at 0.5 fps |
| Change detection | **7–25 ms** | numpy, by resolution | only if row 13 lands |
| Encode 1280 WebP | **57 ms** | Pillow `method=2` | `method=4` costs 2.6× for 3 % |
| Transport, 51 KB frame | **~345 ms** warm | bytes / link | tile diff → ~5 KB → **~40 ms** *(est.)* |
| Decode + swap | ~20 ms *(est.)* | `img.decode()` before swap | already awaited |

**Input latency** (tap → the PC has acted): 133 + 60 ≈ **~200 ms**.
**Screen latency** (ask → pixels shown): 34 + 57 + 345 + 20 ≈ **~460 ms**.
**Full loop** (tap → see the result): ~200 + one refresh ≈ **~660 ms optimistic**.

| Case | Loop | Driven by |
|---|---:|---|
| Optimistic (measured path, warm) | ~0.66 s | as above |
| Expected (client waits 900 ms for slow UI, as it does today) | ~1.2 s | the deliberate second refresh |
| Worst reasonable (`A-002` phone at 20–40 KB/s) | **1.5–3 s** | a 51 KB frame alone takes 1.3–2.6 s |

The worst case is the one that decides row 13, and it rests on an **assumption two versions
old**. That is why E1 is first.

---

# 10. Session architecture

**One operator, one machine, one process.** The honest minimum:

- **Identity** is already solved: `initData` HMAC inside Telegram, `WEB_TOKEN` outside, and a
  single `ALLOWED_USER_ID`. There is no user table to add.
- **Session state needed for the MVP: none.** Every endpoint is idempotent and stateless; the
  screen is pulled, not pushed. The client holds the only state that exists (Click armed, the
  interval, the fold), in `localStorage`.
- **The first real server-side state arrives only with row 13**: a per-client frame baseline
  for tile diffing, keyed by a client id. That is a dict in the process, and its failure mode
  must be designed for — a desynchronised baseline renders a *stale but plausible* screen,
  which is this project's hardest bug class (row 9).
- **No Redis, no DB, no session store abstraction.** Adding one for a single operator would be
  inventing a problem. If a second concurrent viewer ever matters, the dict grows a key; that
  is the whole migration.
- **Reconnect** is already the model: the client chains from completion, pauses when hidden,
  and version-checks itself against `/api/status`. There is no session to lose.

---

# 11. Polling vs webhook

**Read.** `run_polling` with PTB v20 already long-polls (`poll_interval=0.0`, `timeout=10`), so
the added latency is well inside a 2-second refresh. More decisively: **the interactive path
does not use Telegram at all** — clicks and keys go over HTTPS to the local aiohttp app. A
webhook would change the latency of *chat commands only*, and would require exposing an inbound
endpoint that the current architecture deliberately does not have. **Do not change it.**

---

# 12. WebSocket vs HTTP

For the MVP, **chained HTTP POST**, unchanged (`D-011`).

| | chained POST | WebSocket |
|---|---|---|
| Frames | one request per frame, paced by completion | server can push on change |
| Saving | — | ~133 ms per frame *(est.)* |
| Backpressure | **free** — the next request starts when the last finished | must be rebuilt (ack before send) |
| Cost | none, it exists | a second protocol path, reconnect logic, and the tunnel handshake is **untested** |

A WebSocket is worth it **only together with row 13**, where the server has a reason to push
(a tile changed) rather than answer. On its own it saves 133 ms of a ~460 ms budget and buys a
new class of failure.

---

# 13. Security model

| Threat | Standing mitigation | Gap |
|---|---|---|
| Unauthorised Telegram user | single `ALLOWED_USER_ID`; `initData` HMAC with an expiry | — |
| Any `/api/*` reached unauthenticated | **every** handler checks; two tests pin the coverage and the count (`D-010`) | a new route must inherit it — that is the test's job |
| Scope creep of the refine token | `_check_auth_refine` is a separate function, so a bad merge fails **closed** | — |
| Stolen `WEB_TOKEN` | full control of the desktop | no rotation, no audit log — **accepted risk for one operator** |
| Leaked URL | the URL alone is useless without a token or `initData` | — |
| MITM | TLS terminated at Caddy; the tunnel is ssh | — |
| Public topology | host and both VPS addresses are already public in git history | `B-1`, open decision row 4 |
| XSS in the Mini App | the markdown renderer escapes `"`/`'` and allows only http(s)/mailto (`D-010` chunk) | LLM output is rendered in `/refine`, not the dashboard |
| **Opening a VNC server** | **not done** — and this study recommends never doing it | a VNC password is DES-truncated to 8 characters; see §5 |
| Audit | `bot.log` records every injected click, drag and typed length | unrotated, 3.2 GB (row 3) |

**The strongest security property of the current design is architectural:** there is no
listening remote-control service. Port 8080 is bound locally and reached only through an
outbound ssh tunnel the PC itself establishes. Variant C would end that property.

---

# 14. UX findings

The phone-remote-desktop pains gathered at row 10 stand and are not repeated: chrome over the
picture, long-press misread as a held button, gestures colliding with the OS's own, modifier
state desynchronising, and precision work wanting a relative cursor. What this pass adds is
evidence about the two stacks variant C would adopt.

**Guacamole's input model is the cautionary tale, and it validates a choice already made here.**
Its input target is a **canvas, not a real `<input>`**, so on Android the OS keyboard often does
not appear at all; its own built-in fallback keyboard is reported to have keys "impossibly small
to press" on a phone, and touch has to be translated into synthetic mouse events, where a finger
is a very inaccurate pointing device. **Observed**:
https://sourceforge.net/p/guacamole/discussion/1110834/thread/874edc19/
(A widely-cited forum thread titled "Guacamole's Android typing is a nightmare" exists but could
not be fetched — 403 — so it is named, not quoted.)

That is the same wall §7 is about, and it is why this project's typing surface must be a **real
focused form field** rather than a canvas. Guacamole's answer to the same problem — a text-input
mode that diffs the field's value and infers keystrokes — is a second, independent confirmation
that the field is the only reliable capture surface on a phone.

**Chrome Remote Desktop** draws the complaints of a video pipeline: slow sessions, unstable
connections, poor graphics quality and frequent disconnects, with its Android app's rewrite from
native to a web wrapper called buggy by reviewers. **Observed**:
https://www.techradar.com/reviews/chrome-remote-desktop-review

The lesson for a 0.5 fps tool is not "avoid their bugs" — it is that **a continuous stream is a
liability to maintain**, and a request/response screenshot loop has no disconnect state to
recover, no codec to negotiate and no stream to stall. That is a real advantage of the boring
architecture, not a consolation for it.

**Rules carried into §15's changes**, each traceable above:

1. The typing surface is a **real form field**, never a canvas — Guacamole's keyboard problem is
   exactly the one this avoids.
2. Autocorrect and prediction are **defeated at the field** (`type="password"`), because a
   correction cannot be un-injected.
3. Say what the mode can and cannot do: characters land immediately, a predicted word lands when
   the keyboard commits it.
4. Do not adopt a streaming transport to fix a bandwidth problem that does not exist at this
   frame rate.

---

# 15. Changes required in this repository

| Existing file | Proposed change | Reason | MVP / Later |
|---|---|---|---|
| `handlers/input.py` | add `type_unicode(text)` — `SendInput` + `KEYEVENTF_UNICODE`, separate from `press_keys` | direct typing; must not merge with the hotkey path | **MVP** |
| `handlers/web.py` | one route, `POST /api/chars {text}` | the batched keystroke sink | **MVP** |
| `web/index.html` | an always-focused `type=password` field + `beforeinput` handling + batching, armed by a mode toggle | capture the phone keyboard; the password type is what defeats Chrome-Android's suggestion layer (§7.2) | **MVP** |
| `tests/test_input.py` | unicode path, batching contract, and the invariant that modifiers never go through it | this is the bug-prone area of the project | **MVP** |
| `config.py` | `TYPE_BATCH_MS`, `TYPE_UNICODE_MAX` | the two knobs the batch needs — the interval is an engineering choice justified by the 133 ms tunnel, not a cited practice (§7.3) | **MVP** |
| `handlers/screen.py` | per-client baseline + tile encoder | row 13, only if E1 says so | Later |
| `web/index.html` | `<img>` → `<canvas>` | required by tile diffing; invalidates four pieces of tested scar tissue | Later |
| `requirements.txt` | declare `numpy` | already imported by the diff path; currently undeclared | Later (with row 13) |
| `bot.py` / logging | rotation | row 3 — 3.2 GB is an audit log nobody can read | independent |

| Proposed module | Responsibility | Integration point |
|---|---|---|
| *(none)* | — | every change above lands in a file that exists |

**No new module is proposed.** That is deliberate: the smallest correct change to a project
with this much scar tissue is one inside the files that already carry it.

---

# 16. Dependencies

| Dependency | Purpose | Why needed | Alternative | Add for MVP? |
|---|---|---|---|---|
| *(none)* | — | `SendInput` is `ctypes` against `user32`, which the project already uses | — | **No** |
| `numpy` | tile diff | already installed and imported; only undeclared | pure-Python diff, ~100× slower | with row 13 |
| `dxcam` / `windows-capture` | DXGI capture | **not needed** — 34 ms at 0.5 fps is free, and none exposes dirty rects to Python | — | No |
| `vncdotool` / `asyncvnc` | RFB client | only under variant C, which is not recommended | — | No |

**The MVP adds no dependency at all.**

---

# 17. Risks and unknowns

**Known risks**
- Every gesture claim in this project has been green in the suite while broken on the device
  (`D-023`). Tests describe the client; only `bot.log` proves it.
- Direct typing touches the most expensive bug area in the project's history (`D-005`–`D-008`).
- A tile-diff baseline that desynchronises renders a *plausible* stale screen — the failure
  mode that is hardest to notice.

**Unknowns needing an experiment**
- **E2** — does Claude Code in Windows Terminal accept synthesized `WM_CHAR` at speed?
- **E1** — is the phone still at 20–40 KB/s? (`A-002`, two versions old.)
- Does a WebSocket handshake complete through Caddy + the tunnel? (E3, only if row 13 lands.)

**Assumptions**
- `A-002` — the phone's throughput collapse is environmental. Unfalsified, and it decides row 13.
- The operator is the only user, and stays so. Every simplification above rests on this.

---

# 18. Experiments before implementation

| # | Hypothesis | Why it matters | Method | Success criteria |
|---|---|---|---|---|
| **E2** | A `KEYEVENTF_UNICODE` character reaches Claude Code in Windows Terminal at typing speed | decides whether direct typing is possible at all | a disposable script types a marker into a live prompt at 5/10/20/40 cps | every character arrives, in order, at ≥10 cps |

**E2 — PASSED 2026-09-09, against Claude Code in Windows Terminal.** Run twice: the
2026-09-08 attempt confirmed the mechanism but hit the wrong target, and the re-run put the
markers on the real prompt line.

| | 2026-09-08 | 2026-09-09 |
|---|---|---|
| Target | **wrong** — a verified focus was lost 800 ms later, see below | `✳ Claude Code` / `windowsterminal.exe`, held for every burst |
| Latin, digits, punctuation | arrived | **byte-exact at 5, 10, 20 and 50 cps**, all four bursts, in order |
| **Cyrillic** (`Привет_мир`) | arrived — the layout was never consulted, as designed | byte-exact |
| **Emoji** (`🙂`), `✓ ∑ №` | arrived — the UTF-16 surrogate pair path works | byte-exact |
| Speed | 38.3 cps | **52.0 cps effective**, `short_calls: 0` at every rate |

The criterion was *every character arrives, in order, at ≥10 cps*. It arrives at **52**, which
is well above any human typing rate the phone can produce, so the client's batching will be
sized by the link, not by this path.

**Two runs, one guard added between them.** `--require WindowsTerminal` matches the *process*,
and a terminal is one process for **every tab in it** — the 2026-09-09 first attempt passed
that guard and still landed on a `Windows PowerShell` tab. The tab is distinguished by its
**title**, so the script gained `--require-title` and the real run was pinned on
`✳ Claude Code` — which is `D-007` seen from the other side: the process decides
terminal-*ness*, the title is the only thing that says *which* target.

**The one deviation, and it is a rewrite rather than a loss.** `e` + `U+0301` (decomposed é)
came back as `U+00E9` (precomposed). Everything else, including the astral emoji, was identical.
The same rewrite happened in **both** targets — a shell input line and a TUI's own buffer —
which points at the element they share, the copy-to-clipboard used to read the line back, and
not at either reader. *Points at; does not prove.* `e2_readback.py` settles it by reading the
line in-process with `input()` and printing code points, and that run is still owed. It does not
gate row 17: composed and decomposed é render identically, and NFC is what every Windows text
path produces anyway.

Two things the 2026-09-08 run bought that no amount of reading would have:

1. **`sizeof(INPUT)` must be 40 on x64**, because the largest member of the real union is
   `MOUSEINPUT` (32 bytes). A union containing only `KEYBDINPUT` gives 32, and Windows then
   rejects **every** call with `ERROR_INVALID_PARAMETER` (87), sending zero characters. The
   first attempt failed exactly this way. `press_keys` never met it because it uses the legacy
   `keybd_event`.
2. **A verified focus does not stay verified.** `force_foreground()` checks
   `GetForegroundWindow()` and returns honestly — it returned `True`, and PowerShell *was*
   foreground at that instant. **800 ms later Sublime Text held the foreground** and the marker
   went into an unrelated document. This is the same shape as the 2026-08-31 measurement in
   [chunks/features/phase2-screen-input.md](../chunks/features/phase2-screen-input.md), where
   Claude Desktop reclaimed the foreground 700 ms after a successful focus.

**The consequence for the product, not just the experiment.** `POST /api/type` with an explicit
`window` target currently focuses, settles, types, and *then* reports `on_target: false` if the
foreground moved — deliberately, on the rule that "a wrong guess about the foreground must not
eat the text". That rule is right for an **untargeted** send, where the foreground is the
target by definition. It is wrong for a **targeted** one: the text does not vanish, it lands
somewhere real. This run put 62 characters into an editor buffer that way. A targeted send
should **re-check after the settle and refuse**, which is row 19.
| **E1** | The phone still collapses to 20–40 KB/s | decides whether row 13 is feasibility or polish | the existing frame loop from the phone, logged, on the current build | a sustained figure, re-derived in the same run |
| **E6** *(half done)* | Cyrillic, emoji and composed text survive the unicode path — **passed with E2** — **and the client's composition handling**, which still needs the phone | the layout bug class must not return by another door, and predicted Cyrillic words arrive only at `compositionend` (§7.2) | E2's script with mixed-script input, then the same words typed on the phone with prediction on | byte-exact arrival; no `insertReplacementText` corrupting already-sent text |
| **E8** | Tile diff holds up over a real session, not a 6-frame sample | the 2.3 % figure is from one desktop state | log changed-tile ratio for an hour of real work | median < 10 % |
| E3 | A WebSocket completes through Caddy + tunnel | only if row 13 lands | one echo endpoint, one browser console | handshake completes, survives 10 min |

**Priority: ~~E2~~ → E1 → E6 → E8 → E3.** E2 **passed 2026-09-09** and is struck. E6's
*injection* half passed with it (the mixed-script burst was in the same run); what is left of E6
is the half that needs the **phone** — whether a predicted Cyrillic word survives the client's
composition handling, which no desktop script can answer. E6 and E1 both need the operator with
the phone in hand.

---

# 19. MVP scope

**In:** connect (already), screenshot refresh (already), left click, right click, double click,
drag, scroll, named keys and combos (all already) — **plus direct typing**, which is the only
new verb.

**Out of the MVP, explicitly:**

- 30–60 fps video, any video codec, WebRTC
- audio, file transfer beyond the existing path-typing upload
- multi-user, concurrent sessions, roles, a session store
- a VNC/RFB server or client anywhere in the stack
- NAT traversal infrastructure (the tunnel is the answer and it works)
- unattended fleet management
- Linux/macOS targets — the project is Windows-only by design
- tile-diff transport, until **E1** says the link needs it

---

# 20. Implementation plan

| Phase | Task | Modules | Depends on | Acceptance |
|---|---|---|---|---|
| ~~**1**~~ | ~~E2 + E6~~ | disposable script | operator present | ✅ **done 2026-09-09** — byte-exact at 52 cps into `✳ Claude Code`; E6's phone half moves to phase 5 |
| **2** | `type_unicode()` + `POST /api/chars` | `handlers/input.py`, `handlers/web.py`, `config.py` | phase 1 | unit-tested; a test forbids modifiers on this path |
| **3** | Client typing mode | `web/index.html` | phase 2 | a `type=password` field captures the soft keyboard; `beforeinput` primary; composition edges only; batching `TYPE_BATCH_MS`, measured not assumed |
| **4** | Field UX | `web/index.html` | phase 3 | the keyboard does not cover the point being typed at; `hideKeyboard()` on exit |
| **5** | E1 | none | the phone | a throughput figure re-derived today |
| **6** | Row 13 *only if* phase 5 demands it | `handlers/screen.py`, client canvas | phase 5 | tile transport with a full-frame fallback and a resync path |

---

# 21. Final recommendation

**Build direct typing into the Mini App that already exists. Change nothing else.**

- **UI:** the existing Telegram Mini App. Not the chat (it cannot carry coordinates), not an
  external web UI (it adds processes and auth surfaces to replace things that work).
- **Transport:** chained HTTPS POST over the existing tunnel. A WebSocket only if row 13 lands.
- **Remote-control protocol:** **none.** The bot runs on the machine it controls; introducing
  RFB would add a network protocol between two things that share a process.
- **Libraries:** no new dependency. `SendInput` through `ctypes`, as the project already calls
  Win32.
- **Screen:** WebP `method=2`, `BILINEAR` downscale, full frames until E1 proves otherwise.
- **Input:** two paths that never merge — `press_keys` (VK codes) for named keys and combos,
  `KEYEVENTF_UNICODE` for characters.
- **Session:** none. One operator, stateless endpoints, client-side preferences.
- **Security:** unchanged, and the property worth protecting is that **no remote-control service
  listens anywhere**.

**Left for the next iteration:** the tile-diff transport (row 13, gated on E1), the viewer
extraction (row 14), and log rotation (row 3), which is what makes the audit trail usable.
