# Interactive control ("VNC mode") — research pack

**Row 10 · 2026-09-07 · research only, no code was written.**

> **⚠ Superseded by [remote-control-architecture.md](remote-control-architecture.md) (row 18,
> 2026-09-08).** That study asks a wider question — three architecture variants including an
> external web UI, a session model, a threat model and an MVP plan — and it is the current
> answer. **This file stays for its measurements**, which were taken on this machine and are
> cited rather than repeated there: frame redundancy, encode costs, the tunnel round trip and
> the `pyautogui.PAUSE` finding. Read this one for *numbers*, that one for *what to build*.
> Route A of this pack shipped as v0.22.0; `D-017`–`D-020`, `D-023`.

The question: what does an interactive remote-control mode cost *on top of what the
dashboard already does*, and which parts of the brief are already shipped, already
impossible, or worth building.

Every claim below is labelled. **Measured** = a number read off this machine today, with the
command that produced it. **Read** = read out of this repository's own code. **Cited** = an
external source with a URL. **Observed** = a user report. Nothing here is an estimate unless
it says so.

---

## 0. The finding that reframes the brief

**Read.** The brief asks to build screen streaming, click mapping, key passthrough, special
keys and a 2-second refresh. **All five ship today** in the Mini App — `POST /api/frame`
(binary WebP, hash dedup, 204-unchanged), rect-mapped click-on-image with a tap-delay
double click, `POST /api/key` via virtual-key codes, a 20-button key rail, and a chained
auto-refresh with a 1/2/3/5/10s selector. See
[chunks/features/web-dashboard.md](../chunks/features/web-dashboard.md) and `D-011`.

So this is not a greenfield "add VNC" project. It is **four missing verbs and one transport
problem**:

| Brief asks for | State today | Where |
|---|---|---|
| Screenshot stream @2s | **ships** — `/api/frame`, `_autoSchedule()` | `handlers/web.py:107`, `web/index.html:1149` |
| Click on image → remote click | **ships** — rect mapping in two places | `web/index.html:1301`, `:1538` |
| Double click | **ships** — 280ms tap-delay upgrade | `web/index.html:1315` |
| **Right click** | **missing** — `/api/click` has no `button` | `handlers/web.py:294` |
| **Drag / mouse down-up** | **missing** — no endpoint at all | — |
| Text typing | ships, but **clipboard-paste based**, not keystrokes | `handlers/input.py:139` |
| Special keys, combos, F1–F12 | **ships** — `_VK` table, layout-proof | `handlers/input.py:76` |
| Diff / partial-frame transfer | **missing** — whole frame or nothing | `handlers/web.py:107` |

The rest of this document is about those rows and the transport under them.

---

## 1. Measured: the machine, today

Commands are in [the appendix](#appendix--how-these-numbers-were-produced). Screen is
2048×1152, single monitor, Python 3.14.3, mss 10.1.0, Pillow 12.1.1, pyautogui 0.9.54.

### 1.1 Capture and encode

**Measured.** `mss` full-screen grab: **min 27.8 / median 33.7 / max 45.5 ms** over 8 grabs.

| Width | JPEG q70 | WebP q70 m2 | WebP q70 m4 | WebP q50 m2 |
|---|---|---|---|---|
| 1280 | 80.7 KB / 16.7 ms | **45.3 KB / 57.8 ms** | 43.5 KB / 60.0 ms | 38.4 KB / 23.2 ms |
| 1920 | 163.0 KB / 2.9 ms | **86.3 KB / 49.6 ms** | 83.2 KB / 127.7 ms | 74.0 KB / 48.7 ms |
| 2048 | 198.9 KB / 4.1 ms | 110.6 KB / 58.7 ms | 106.4 KB / 144.4 ms | 95.7 KB / 55.8 ms |

WebP m2 is **44–47% smaller** than JPEG at the same nominal quality and costs ~50 ms more.
At a 2-second cadence 50 ms is free. `method=4` buys another 3% for 2.6× the encode time —
the existing choice of `method=2` (`handlers/screen.py`) is confirmed, not merely inherited.

### 1.2 The pipe

**Measured**, curl from this PC, cold TLS on every call, so the connect/TLS columns are a
worst case a browser with keep-alive does not pay:

| Call | conn | TLS done | TTFB | total | bytes |
|---|---|---|---|---|---|
| local `GET /api/layout` | — | — | 1.6 ms | **1.7 ms** | 192 |
| tunnel `GET /api/layout` | 70 ms | 147 ms | 280 ms | **287 ms** | 192 |
| local `POST /api/frame` 1280 webp | — | — | — | **82–91 ms** | 51.5 KB |
| tunnel `POST /api/frame` 1280 webp | 70 ms | 142 ms | 360 ms | **483–552 ms** | 51.5 KB |
| tunnel `POST /api/frame` 1920 jpeg | 71 ms | 141 ms | 342 ms | 534 ms | 181 KB |
| tunnel `POST /api/frame` 1920 webp | 69 ms | 140 ms | 380 ms | 570 ms | 100 KB |

Subtracting the handshake: **a warm control round trip through the tunnel is ~133 ms**, and a
51 KB frame lands ~345 ms after it is asked for. That is the interactivity floor, and it is
good news — the tunnel is not the bottleneck people assume it is.

The path measured is PC → internet → VPS → ssh tunnel → PC, so **the PC's uplink is counted
twice**; a phone's path is shorter on one leg and longer on the other. This approximates the
phone's experience, it does not substitute for measuring it — and `A-002` records the phone
at 20–40 KB/s, where a 51 KB frame takes **1.3–2.6 s** and the 2-second target is missed by
the transport alone.

### 1.3 The redundancy — the number this whole document turns on

**Measured**, live desktop, VS Code and a terminal open, nothing being typed:

- **0 of 5** consecutive whole frames were byte-identical. The `X-Hash` / `204 Not Modified`
  dedup in `/api/frame` therefore **essentially never fires on a working desktop** — a
  blinking caret invalidates the entire frame.
- Yet only **0.87 – 2.6 %** of 64-px tiles changed per 500 ms step (11.3 % on the busiest).
  At 2-second steps: **2.3 %, 15.6 %, 2.4 %**.
- Computing the tile mask costs **15.4 ms** with numpy at 2048×1152 (a 32×18 grid of 64 px).

Payload for the same steps, WebP q70 m2, against a 50.5 KB full 1280 frame:

| changed tiles | union bbox | **packed tile strip** |
|---|---|---|
| 13 / 576 (2.3 %) | 832×512 → 31.0 KB / 14 ms | **4.9 KB / 2 ms** |
| 90 / 576 (15.6 %) | 896×960 → 58.0 KB / 25 ms | **37.1 KB / 13 ms** |
| 14 / 576 (2.4 %) | 768×512 → 27.9 KB / 11 ms | **6.3 KB / 2 ms** |

Two conclusions, both load-bearing:

1. **Tile diffing wins 8–10× on a typical step** and degrades to "no worse than a full frame"
   on a busy one. 51 KB → 5 KB is the difference between missing and hitting the 2 s budget
   on the `A-002` phone.
2. **The union bounding box is a trap.** A caret in one corner and a clock in the other make
   the bbox the whole screen while 2 % of pixels changed. Anyone implementing this reaches
   for the bbox first because it is ten lines; the measurement above is why not to.

### 1.4 The 100 ms nobody knows about

**Measured.** `pyautogui.PAUSE` defaults to **0.1 s and nothing in this repo changes it** —
`handlers/input.py` sets `FAILSAFE = False` and stops there.

```
moveRel(0,0) with PAUSE=0.1 : 100.5 ms
moveRel(0,0) with PAUSE=0   :   0.1 ms
```

**Read.** `pyautogui.click(x, y)` moves and then clicks — two paused calls. So every remote
click spends **~200 ms sleeping**, and `utils/mouse.scroll_at` (moveTo → scroll → moveTo)
spends **~300 ms**, on top of the ~133 ms tunnel round trip. A drag built the obvious way
(moveTo, mouseDown, moveTo, mouseUp) would spend **~400 ms** asleep before anything is sent.

This is the cheapest latency win available and it is one line. It is also not free to change
blindly: `PAUSE` is what stops injected events arriving faster than a target window's message
loop drains them, so the fix is `PAUSE = 0` **plus deliberate sleeps** where a sequence needs
settling — the discipline `TYPE_ENTER_DELAY` already encodes (`D-005`).

### 1.5 Environment constraints found while measuring

- **numpy 2.4.4 is installed but is not in `requirements.txt`.** A tile-diff path makes it a
  real dependency and it must be declared. (`websockets 16.0` is likewise installed and
  undeclared; aiohttp has its own WebSocket support and does not need it.)
- `dxcam` 0.3.0, `d3dshot` 0.1.5 and `windows-capture` 2.0.1 all **resolve** on
  `pip install --dry-run`, but this box runs **Python 3.14.3** and none of them is verified to
  import there — dxcam's last release is 2022. Treat "we can have Desktop Duplication dirty
  rects from Python" as **unverified** until one is installed in a throwaway venv.
- **Caddy forwards a WebSocket upgrade to the origin** — a request carrying
  `Upgrade: websocket` reached aiohttp and was answered by aiohttp, not intercepted by Caddy.
  Evidence the hop is transparent, not proof the handshake completes; a real `/api/ws`
  endpoint is a 15-minute test.

---

## 2. Input — the brief's three requirements, answered

### 2.1 Right click = **two-finger tap** (operator's ruling, 2026-09-07)

The brief said "double click on the image = right click"; the operator corrected it during
this session to **two-finger tap**, which is the trackpad convention and is right — the
double-tap is already spent twice over: 280 ms tap-delay upgrades to a remote *double click*
(`web/index.html:1315`), and in the zoomed viewer double-tap toggles fit↔3× zoom.

**Read — the exact obstacle.** The lightbox gesture machine (`web/index.html:1430–1500`)
already tracks every pointer in `_lb.ptrs` and sets `_lb.multi = true` the moment a second
one goes down; `pointerup` then returns early on `multi`. **A two-finger tap today is
deliberately swallowed**, so the tail of a pinch cannot be read as a tap — that guard was
written after a real bug where a pinch closed the viewer.

The work is therefore not "add a gesture", it is "split one flag in two":

- `multi` currently means both *"two fingers were down"* and *"this was a pinch"*. A
  two-finger **tap** is the first without the second.
- The 2-pointer branch of `pointermove` sets `_lb.moved = true` **unconditionally**, on any
  jitter. A two-finger tap on a phone always jitters, so it needs the same `|dx|+|dy| > 3`
  threshold the 1-pointer branch already uses, or the gesture can never fire.
- Fire on the **last** `pointerup` when: peak simultaneous pointers was exactly 2, neither
  moved past threshold, and the whole gesture took under ~300 ms. Anchor at the midpoint of
  the two down-points, mapped through the same `lastRect` inverse as `_lbClickAt`.
- The un-zoomed `#screen-area` image has no pointer machine at all (just `img.onclick`), so
  it needs a small one or the gesture is viewer-only. Viewer-only is defensible for a first
  cut — the zoomed view is where precise pointing happens.

**Server side is trivial.** `POST /api/click` takes `{x, y, double}` and calls
`pyautogui.doubleClick` or `.click`. pyautogui 0.9.54 on this machine exposes `rightClick`,
`middleClick`, `mouseDown`, `mouseUp`, `dragTo`, `tripleClick` — verified. A `button` field
(`left|right|middle`) is a three-line change; `down`/`up` for drag is another five.

### 2.2 Instant text entry after a click

**Read.** Today: tap the field on the screenshot → the click lands → type into the freeform
field in the bottom bar or the viewer → `POST /api/type` → clipboard write + a paste hotkey
chosen from the target process + `TYPE_ENTER_DELAY`. The text is **pasted, not typed**, and
that is scar tissue: `pyautogui.write` garbles long text, the paste key depends on the target
window (`D-006`, `D-007`), and Enter must not follow a paste immediately (`D-005`).

For interactive mode the missing piece is not a protocol, it is a **keystroke path that skips
the clipboard** — a word, a `y`, a password does not want a clipboard round trip, and every
clipboard write stomps on whatever the operator had copied.

**The candidate is `SendInput` with `KEYEVENTF_UNICODE`**, which carries the character itself
rather than a key position and therefore **cannot be mangled by the active keyboard layout** —
precisely the failure that made the whole bot mute under Russian (v0.21.0,
[chunks/features/phase2-screen-input.md](../chunks/features/phase2-screen-input.md)).
`press_keys()` solved the *named-key* half of that with virtual-key codes; unicode injection
is the *character* half, and together they remove the clipboard from the fast path.

**Unverified on this machine.** A unicode `SendInput` produces `WM_CHAR`; whether Windows
Terminal, the VS Code integrated terminal and Claude Code all accept it at speed is an
experiment, not a citation.

### 2.3 Special keys — already done, and better than the brief assumes

**Read.** `_VK` (`handlers/input.py:76`) maps modifiers, Enter/Tab/Esc/Space/Backspace/
Delete/Insert/Home/End/PgUp/PgDn, all four arrows, `a`–`z`, `0`–`9` and **F1–F12**; sends
them as virtual-key codes down-in-order/up-in-reverse; and sets `KEYEVENTF_EXTENDEDKEY` on
the keys whose numpad twins would otherwise arrive under NumLock. Combos are several names
(`ctrl+c`, `shift+tab`). `POST /api/key` takes `{key, repeat, interval}`.

The brief's third input requirement is **shipped**. The open question is UI, not protocol: 20
buttons exist in `KEYS` (`web/index.html:736`) and the bottom bar folds (`D-016`). What is
missing is **sticky modifiers** — no way to hold Ctrl while tapping the screenshot — and that
is a UI state machine, not an endpoint.

**One real gap:** `press_keys` uses `keybd_event`, the legacy API, not `SendInput`. It still
works (Windows maps it onto SendInput internally) but it cannot batch a key and a mouse event
atomically, which is what Shift+drag-to-extend-a-selection needs. Worth knowing before drag
is built.

---

## 3. Transport — how frames should move

### 3.1 The chained-request rule stands (`D-011`)

Anything on a timer chains from the previous request's *completion*, never `setInterval` — a
fixed interval piles up in the single reverse-SSH pipe and the live view stops updating.
`_autoSchedule()` already does this and nothing measured here challenges it.

### 3.2 What a diff transport looks like, given §1.3

- The server keeps **the last frame it sent to each client**, keyed per client — two viewers
  must not corrupt each other's baseline.
- Per request: grab, compute the 64-px tile mask against that baseline (15 ms), encode the
  changed tiles as **one packed strip** plus a small manifest of `(tile_index, strip_x)`.
- The client blits the strip's tiles into a `<canvas>` at their grid positions.
- Full frame instead when changed tiles exceed ~40 % (scene change), or the client has no
  baseline (first frame, reconnect, restored tab).
- 64 px beat 128 px by ~2× in changed-area terms — a caret is small, and a bigger tile drags
  untouched pixels along with it.

**The honest cost:** the client stops being an `<img>` and becomes a canvas, which
invalidates the flicker-free swap, the decode-before-swap fix, the `_capSeq` race guard and
the lightbox's `naturalWidth`-based coordinate inverse — all scar tissue with tests behind it
(`test_frame_swap_waits_for_decode`). That is the price of a 10× bandwidth win, and it is why
this is a route to decide rather than a foregone conclusion.

### 3.3 WebSocket versus chained POST

A WebSocket removes a round trip per frame (~133 ms warm) and lets the **server** push when
the screen actually changed instead of being asked every N seconds. The tunnel appears to
forward the upgrade (§1.5). But it hands the pacing to the server, which is what `D-011`
warns about on a thin pipe — the backpressure that chaining gives for free must be rebuilt
explicitly (send only after the client acks). Worth it together with §3.2; on its own it
saves 133 ms of a ~480 ms budget.

---

## 4. External research

Three parallel passes: RustDesk/AnyDesk internals, Telegram API limits, phone-remote-desktop
UX. Only the findings that change a decision here are kept; each carries its source.

### 4.1 Telegram — the chat surface cannot do this, at all

**Cited.** *A bot can never learn where on a photo a user tapped.* The chat surface exposes
`callback_query` (button identity, not position), `message_reaction` (admin-gated, opt-in via
`allowed_updates`, and never fired for a bot's own reactions), replies and commands. No update
type carries touch coordinates on media. https://core.telegram.org/bots/api

The closest approximation is an inline-keyboard grid — buttons render *below* the photo, not
over it, and the practical ceiling is roughly 8 per row and ~100 per message with 64-byte
`callback_data`. That is **tens of zones for a 2-million-pixel frame**. The brief's §1.1
("двойной клик по изображению в Telegram") is therefore not a design choice to make; on the
chat surface it is impossible, and on the Mini App it is already solved.

Also worth having on record, since the brief asks about a 2-second chat refresh:

- `editMessageMedia` with `attach://` does replace a photo in place, keeping the same
  `message_id` and chat position. **Cited**, same URL. Whether the rendered image flickers is
  undocumented and unmeasured — treat as untested.
- Telegram's FAQ gives ~1 message/second per chat, ~30/second across chats, 20/minute per
  group, and says *"messages"* — it never states whether **edits** share that bucket. Every
  claim that they do is secondary. A 0.5 Hz loop is comfortably under either reading, but the
  number is an assumption, not a citation. https://core.telegram.org/bots/faq
- `sendPhoto` re-compresses through Telegram's own JPEG pipeline (10 MB, width+height ≤ 10000,
  ≤ 20:1). `sendDocument` preserves bytes and loses the inline preview. For a screenshot whose
  point is legible text, that trade matters.
- `answerCallbackQuery` has a hard ~10 s window; the pattern is answer immediately, then do
  the work and edit. Tap-to-handler latency has no published figure and would have to be
  measured.
- python-telegram-bot v20's `run_polling` already long-polls (`poll_interval=0.0`,
  `timeout=10`), so polling adds well under the 2 s budget. Webhook-vs-polling is an infra
  choice here, not a latency one.

**Mini App APIs worth knowing before building gestures** (Bot API version in brackets,
https://core.telegram.org/bots/webapps):

| API | Why it matters here |
|---|---|
| `disableVerticalSwipes()` [7.7] | **Load-bearing for drag.** Telegram's own swipe-down-to-close would otherwise eat a vertical drag gesture on the screenshot |
| `safeAreaInset*` / `--tg-safe-area-inset-*` [8.0] | the notched-iPhone bottom-bar problem already listed as known-unfixed in v0.21.0 |
| `requestFullscreen()` [8.0], `lockOrientation()` [8.0] | more screenshot, less chrome — see the first UX rule below |
| `HapticFeedback` [6.1] | the only confirmation a remote click has landed that costs no pixels |
| `hideKeyboard()` [9.1] | reclaim the half-screen the phone IME takes after typing |

### 4.2 RustDesk / AnyDesk — what transfers and what does not

**Read.** RustDesk captures through DXGI Desktop Duplication and encodes with hardware
H.265/H.264, then AV1/VP9/VP8, with a VRAM path that avoids GPU→CPU→GPU copies.
https://deepwiki.com/rustdesk/rustdesk/5.1-video-capture-and-encoding · **None of that
transfers.** That machinery exists to amortise cost across a continuous 30 fps stream; a
0.5 fps loop sends independent stills, where inter-frame prediction buys nothing and buys it
in exchange for owning encoder state, keyframe negotiation and jitter handling.

AnyDesk's DeskRT is closed; public material only says it is a codec specialised for GUI
content — flat regions, sharp edges, scroll detection. Nothing implementable from it.

What does transfer, and it is a lot:

- **`SendInput` with `KEYEVENTF_UNICODE` is the answer to §2.2.** Set `wVk = 0`, put the
  UTF-16 code unit in `wScan`, flag `KEYEVENTF_UNICODE`; Windows delivers `VK_PACKET` and
  `TranslateMessage` turns it into a `WM_CHAR` carrying exactly that character. **There is no
  `VkKeyScanW` anywhere in that path**, so it is layout-independent by construction — the
  bug class that made this bot mute under Russian cannot occur.
  https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-keybdinput
- **And the caveat that shapes the design:** a synthetic held Ctrl does **not** combine with a
  `KEYEVENTF_UNICODE` key the way a real one does. So character injection and hotkey injection
  must stay **two separate paths** — which is exactly the shape this repo already has
  (`press_keys` for named keys and combos, a future unicode path for text). They must never be
  merged into one "send this string" helper. Corroborated by the same limitation in AutoHotkey.
- **`MOUSEEVENTF_ABSOLUTE` maps to the primary monitor only** unless `MOUSEEVENTF_VIRTUALDESK`
  is added — the fix for the multi-monitor gap in §7, when there is ever a second monitor.
  https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput
- **There is no "double click" primitive in RustDesk's protocol.** Its `MouseEvent.mask` packs
  event type (Down/Up/Move/Wheel) and button; a double click is two ordinary Down/Up pairs
  inside Windows' own `GetDoubleClickTime` (default **500 ms**), and drag is Down → Moves → Up
  on the same mask. https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getdoubleclicktime
  **This validates keeping the double click server-side:** two clicks sent as separate HTTP
  requests would be ~133 ms of tunnel apiece plus ~200 ms of `PAUSE` each and would blow
  through the 500 ms window. `pyautogui.doubleClick` in one request is the correct shape.
- **RustDesk's only real backpressure is that the client acks a frame before the next is
  captured** — the same rule as `D-011`, arrived at independently.

And the finding that settles Route D: **no actively-maintained Python package exposes DXGI's
`GetFrameDirtyRects` / `GetFrameMoveRects`.** `mss` is GDI `BitBlt` with none; `dxcam` is
DXGI-based but full-frame-only in its public API; `d3dshot` was archived in August 2022;
`windows-capture` wraps Windows.Graphics.Capture and its dirty-region exposure *to Python* is
unconfirmed. Getting real dirty rects means writing a `comtypes` binding to
`IDXGIOutputDuplication` by hand. Against that, §1.3 measured a numpy diff at 15 ms — the
external recommendation and the local measurement agree: **diff the frame you already have.**

On encoding: WebP is the right choice and AVIF is not — its size advantage comes from
photographic content and evaporates on flat UI, while costing several times the encode.
Blog-sourced, lower confidence, but consistent with §1.1's own numbers. One thing worth
carrying into a test: lossy artefacts on **text** start showing below roughly q80, and this
project ships q70. Size is measured; legibility is not. That is a gap.

### 4.3 UX — what people actually complain about

Every finding here is a user report with a URL.

- **Two-finger tap is the right call, and it is the industry one.** Moonlight's documented
  trackpad-mode gesture set is: one-finger tap = left click, tap-and-hold = drag, **two-finger
  tap = right click**, three-finger tap = keyboard.
  https://github.com/moonlight-stream/moonlight-android/wiki/Setup-Guide · Microsoft's RD
  client uses two-finger tap in pointer mode and long-press only in direct-touch mode.
  https://learn.microsoft.com/en-us/previous-versions/remote-desktop-client/whats-new-ios-ipados
- **Long-press is the gesture people ask to have replaced.** Moonlight's long-press-for-right-
  click was reported as making the PC think the *left* button was being held:
  "The long-press behavior will make the PC think that the left mouse button is long-pressed,
  which makes us get wrong results." https://github.com/moonlight-stream/moonlight-android/issues/1064
- **A gesture that collides with the phone OS's own gesture is a two-year-old bug.** RustDesk's
  three-finger scroll fires Xiaomi's screenshot instead: "Scrolling with three fingers already
  is assigned for screenshot in my Android device." Still open.
  https://github.com/rustdesk/rustdesk/discussions/7277 — and on Telegram the equivalent
  collision is the swipe-down-to-close that `disableVerticalSwipes()` exists to stop (§4.1).
- **Modifier state desyncs, and users notice.** RustDesk's Shift sticks between the phone IME
  and the host: "tapping the shift key on the Android keyboard will hold down shift even after
  you type a letter." https://github.com/rustdesk/rustdesk/discussions/14442 — the rule that
  follows is that a modifier must be **visible, explicit UI state**, never an inferred key-up.
- **Chrome over the picture is the single most repeated complaint.** TeamViewer:
  "the orange border or orange button invades screen space and stops them from accessing that
  portion of the screen." https://apps.apple.com/us/app/teamviewer-quicksupport/id661649585 ·
  RustDesk's own widgets cover the on-screen keyboard.
  https://github.com/rustdesk/rustdesk/discussions/7183 · AnyDesk, App Store: "the touch
  control is very hard to use for clicking small buttons on my desktop screen."
- **Precision work wants a trackpad cursor, not direct touch.** Microsoft: "touch screen input
  is less precise than the mouse cursor and most users prefer the mouse cursor mode."
  https://learn.microsoft.com/en-us/previous-versions/remote-desktop-client/remote-desktop-ios-ipados
  · Jump Desktop's trackpad mode is what reviewers say the app is worth paying for. Splashtop
  ships both modes *and* a touch-offset calibration for devices whose coordinates land off
  target. https://support-splashtopbusiness.splashtop.com/hc/en-us/articles/212724403
- **The messenger-bot category is a different contract.** The three most complete
  Telegram remote-control bots on GitHub (`lazuardyk/Remote-PC-Telegram` ~50★,
  `Antcating/telegram-remote-bot` ~24★, `OmniCtrl`) are all screenshot-on-demand with explicit
  command buttons — no live view, no gesture vocabulary, text sent as a whole buffer. None of
  them has this project's live loop, and none has hit the IME and paste-target problems
  documented in `phase2-screen-input.md`, because none of them types per keystroke. This
  project is already past that category; it should not import gestures that only feel right on
  a 30 fps feed.

**The eight rules, ranked, each traceable above:** (1) never put chrome over the pixels the
user is aiming at; (2) offer a relative-cursor mode where precision matters, direct touch is
the fallback; (3) right click must be a gesture that cannot be misread as a held left button
— two-finger tap, not long-press; (4) route text through the phone's own keyboard, never the
host's on-screen one; (5) modifiers are visible, explicit, stateful UI; (6) if coordinates can
be systematically off, offer calibration rather than hope; (7) never assign a gesture the OS
or Telegram has already claimed; (8) a poll-based screenshot tool should lean into big
unambiguous targets rather than pretending to be a cursor.

Rule 1 has teeth here: `#lb-keys`, `#lb-proj-row` and the freeform field all float **over the
screenshot** in the zoomed viewer. `D-016` already fought this fight for the scroll arrows.

---

## 5. Routes

Four ways to spend the next iteration, ranked. They are not exclusive — A is a prerequisite
for enjoying any of the others — but they are separable, and the roadmap should carry them as
separate rows.

### Route A — the four missing verbs, on the surface that already works *(recommended first)*

Right click by two-finger tap, drag by press-and-hold-then-move, `PAUSE = 0` with deliberate
sleeps, and a `button` field on `/api/click`. No new transport, no new dependency, no canvas.

- **Cost:** small. Three server-side edits inside existing handlers; one gesture-machine
  change in the lightbox (§2.1), which is the delicate part and needs its own test.
- **Buys:** the two verbs a phone user actually misses. Context menus and text selection are
  the difference between "I can look at my PC" and "I can use my PC".
- **Risk:** the gesture split (§2.1) touches code with a bug history — a pinch that closes
  the viewer, a tap that pans. It needs the same treatment `D-016` got: a test per rule.

Three things the external research adds to this route, none of them optional:

- **`disableVerticalSwipes()` must be called before drag ships.** Telegram's own
  swipe-down-to-close gesture will otherwise eat a vertical drag on the screenshot, and the
  user will read it as "the app closes randomly". Rule 7 above, and RustDesk's two-year-old
  three-finger bug is what ignoring it looks like.
- **The double click stays server-side.** Windows merges two click pairs into a double click
  only inside `GetDoubleClickTime` (500 ms); two HTTP requests through this tunnel cannot make
  that window (§4.2). The current single-request `doubleClick` is correct — do not "simplify"
  it into two clicks.
- **A modifier, if one is added, is visible stateful UI** — never inferred from a key-up.
  That is the RustDesk stuck-Shift bug, and it is the one thing that makes a remote keyboard
  feel broken rather than slow.

### Route A′ — a relative-cursor ("trackpad") mode

Not in the brief, but it is the most-cited UX finding in §4.3 and it is small: a visible
cursor the finger drags, tap = click where the cursor is. Direct touch stays as the default.

- **Cost:** small-to-medium, and entirely client-side — the cursor is a DOM element over the
  frame; only the existing `/api/click` is called, at the cursor's mapped position.
- **Buys:** precision. Microsoft, Jump Desktop and Splashtop all ship both modes and all say
  the same thing: for small targets people prefer the cursor. A finger is ~9 mm wide and a
  window's close button, mapped back through a 1280-px frame on a 390-px screen, is smaller
  than that.
- **Note:** it also makes the two-finger-tap right click unambiguous, because the anchor
  becomes "wherever the cursor is" rather than "the midpoint of two fingers".

### Route B — the tile-diff transport

§3.2. Server keeps a per-client baseline, sends a packed strip of changed 64-px tiles, client
blits into a canvas.

- **Cost:** the largest of the four. numpy becomes a declared dependency; the client's image
  pipeline is rewritten and four separate pieces of scar tissue have to be re-earned on a
  canvas (§3.2).
- **Buys:** **8–10× less bandwidth on a typical step** (measured: 51 KB → 5 KB), which is the
  only thing that makes a 2-second refresh survivable on the link `A-002` describes.
- **Do it when:** the phone's real throughput has been re-measured (`A-002` is an *assumption*
  and it is two versions old). If the phone is fine today, Route B buys latency, not
  feasibility, and drops below Route C.

### Route C — a keystroke path that skips the clipboard

§2.2. `SendInput` + `KEYEVENTF_UNICODE` behind the existing `/api/type`, chosen for short
bursts, clipboard kept for long text.

- **Cost:** medium, and front-loaded on an experiment: does Claude Code in Windows Terminal
  accept synthesized `WM_CHAR` at speed?
- **Buys:** typing that does not stomp the operator's clipboard, no `TYPE_ENTER_DELAY`
  bracketed-paste dance for short input, and immunity to the layout bug by construction
  rather than by table lookup.
- **Risk:** it re-opens the single most expensive bug area in this project's history. Any
  change here needs the two-run manual test written in `phase2-screen-input.md` — click into
  the terminal prompt, send, then click into an editor tab and send again.
- **The constraint that must be designed in from the first line** (§4.2): a synthetic Ctrl
  does not combine with a `KEYEVENTF_UNICODE` character. Text injection and hotkey injection
  are **two paths that never merge**. `press_keys()` keeps the combos; unicode gets the
  characters; a helper that takes "a string, possibly with modifiers" is the bug waiting to
  be written.

### Route D — an actual VNC client, or Desktop Duplication

Run a VNC server on the PC and speak RFB from Python, or capture through DXGI Desktop
Duplication for hardware dirty rects.

- **Cost:** highest, and the ceiling is a Python 3.14 dependency that nobody has verified
  imports (§1.5).
- **Buys:** dirty rectangles from the OS instead of computed ones — which §1.3 shows can be
  computed in 15 ms anyway, on a 2-second budget where 15 ms is noise.
- **And the external pass closed the door further** (§4.2): **no maintained Python package
  exposes `GetFrameDirtyRects` at all.** `mss` is GDI, `dxcam` is full-frame-only, `d3dshot`
  was archived in 2022, `windows-capture`'s Python dirty-region exposure is unconfirmed. The
  route is a hand-written `comtypes` binding, not a `pip install`. A local VNC server plus a
  Python RFB client is the other half of this route and is worse: a second process, a second
  auth surface, a second port, to inherit a diff this project can compute in 15 ms.
- **Verdict: not now, and the reason is written down.** Revisit only if the refresh target
  drops below ~200 ms, where a 34 ms grab plus a 15 ms diff stops being free.

### The stack, concretely

The brief asks for a named stack. It is almost entirely the one already installed — which is
the point of §0, and the reason this is a cheap iteration rather than a rewrite.

| Layer | Choice | Why not the alternative |
|---|---|---|
| Capture | **`mss`** (installed) | `dxcam`/`windows-capture` are faster at raw fps, which a 0.5 fps loop cannot spend; neither exposes dirty rects to Python anyway (§4.2) |
| Diff | **numpy tile mask, 64 px** — must be added to `requirements.txt` | DXGI dirty rects need a hand-written `comtypes` binding; the numpy diff costs 15 ms (§1.3) |
| Encode | **Pillow WebP, `method=2`** (installed) | AVIF is slower and its advantage is photographic, not UI (§4.2); JPEG is 45% bigger at the same quality (§1.1) |
| Transport | **aiohttp, chained POST** (installed); WebSocket only alongside Route B | `setInterval` is `D-011`; a WS alone saves 133 ms of a 480 ms budget (§3.3) |
| Mouse | **`pyautogui`** with `PAUSE = 0` and deliberate sleeps | direct `SendInput` buys `MOUSEEVENTF_VIRTUALDESK` — worth it only when a second monitor exists (§7) |
| Named keys / combos | **`press_keys()` virtual-key codes** (shipped) | layout-proof already; do not route combos through unicode injection (§4.2) |
| Text characters | **`SendInput` + `KEYEVENTF_UNICODE`**, new, separate path | the clipboard path stays for long text; the two must not merge (Route C) |
| Client | **the existing Mini App** | the chat surface cannot report a tap position at all (§4.1) |
| VNC / RFB | **none** | a second server, port and auth surface to inherit a diff we compute in 15 ms (§4.2) |

---

## 6. Open experiments — what must be measured before any of this is designed in

Each of these is a claim this document could not settle, with the instrument that settles it.
None takes more than an afternoon; all of them are cheaper than finding out afterwards.

| # | Question | Instrument | Blocks |
|---|---|---|---|
| E1 | Does the phone still collapse to 20–40 KB/s? | the same frame loop from the phone, logged, on the current build — re-derive, never compare to the 2026-07-23 figure | whether Route B is *feasibility* or *polish* (`A-002`) |
| E2 | Does `SendInput` + `KEYEVENTF_UNICODE` land in Claude Code inside Windows Terminal, and at what characters-per-second? | a throwaway script typing a marker into a live prompt, exactly like the v0.19.1 elimination | Route C |
| E3 | Does a WebSocket complete its handshake through Caddy + the reverse-SSH tunnel? | one `/api/ws` echo endpoint and a browser console | §3.3 |
| E4 | Does any Desktop Duplication binding import on Python 3.14? | `pip install dxcam` in a throwaway venv, then one `grab()` | Route D only |
| E5 | Does `PAUSE = 0` break anything that currently works? | the existing suite, then the two-run manual typing test | Route A |
| E6 | Is q70 WebP still legible for **text** on a phone? | the same VS Code frame at q60/70/80/near-lossless, read on the phone, sizes recorded beside each | every quality decision — size is measured, legibility is not (§4.2) |

**Not an experiment:** whether `editMessageMedia` can carry a 2-second refresh in the chat.
It can, and it does not matter — §4.1 shows the chat surface can never report where a tap
landed, so a chat-based live view is a picture, not a control surface. Anything interactive
belongs in the Mini App, which is where it already is.

## 7. Risks and limits

- **The one-pipe rule (`D-011`) binds anything added here.** Two clients, or one client and a
  scheduled job, share the reverse-SSH tunnel. A diff transport with a per-client baseline
  makes that sharing explicit for the first time; a bug there desynchronises a viewer
  silently, and a desynchronised canvas looks like a stale screenshot, which is the hardest
  class of bug this project has (`row 9`).
- **Every remote click lands on the operator's live desktop.** There is no sandbox and no
  undo. Right click and drag are strictly more dangerous than what exists — a drag can move a
  file, resize a window, or select-and-replace text. Whatever ships needs the same treatment
  the Type path got: report where the event actually landed, never a cheerful "clicked".
- **Multi-monitor is unhandled today** and this machine cannot reveal it: `sct.monitors[1]`
  and `pyautogui.size()` both describe the primary monitor only. A second monitor to the left
  gives negative X coordinates, which the rect mapping would send as-is. Untested, and it
  will stay untested until there is a second monitor.
- **`pyautogui.FAILSAFE` is disabled from `handlers/input.py` as an import side effect.** A
  process that imports only `handlers.web` keeps the default `True`, and a click mapped to
  `(0, 0)` — the top-left pixel, which a phone tap on a letterboxed image can produce —
  raises `FailSafeException` instead of clicking. Currently masked because the bot imports
  everything; it is a trap for any future split.
- **Security is unchanged but the blast radius is not.** Every `/api/*` handler checks auth
  (`D-010`) and the new verbs would inherit that. But a scoped `refine.*` token must never
  reach them, and the two invariant tests that pin the auth coverage and the handler count
  are what stop that happening by accident.

---

## Appendix — how these numbers were produced

Every number in §1 came from one of these, run on this machine on 2026-09-07. They are here
so the next session can re-derive the baseline in the same run rather than trusting a figure
from an afternoon that is over (`.claude/rules/verification.md`).

**Capture and encode (§1.1)** — `mss` grab timed over 8 iterations, then `Image.save` into a
`BytesIO` at each width and format, timed with `perf_counter`.

**The pipe (§1.2)** — `curl` with
`-w 'conn=%{time_connect} tls=%{time_appconnect} ttfb=%{time_starttransfer} total=%{time_total} size=%{size_download}'`
against `http://127.0.0.1:8080` and `https://bot.magerash.com`, three runs each, bearer token
from `.env`. Cold TLS on every call — a browser reusing a connection does not pay
`conn`+`tls`, which is why "warm RTT" is quoted as `ttfb − tls`.

**Redundancy (§1.3)** — six grabs 500 ms apart and four grabs 2 s apart, converted to numpy
arrays; `(a != b).any(axis=2)` reshaped into a 64-px and a 128-px tile grid; changed tiles
counted, then re-encoded three ways (full frame, union bbox, tiles concatenated into one
strip) to compare payloads. The whole-frame md5s were compared over the same series to show
the `204` path never fires.

**pyautogui PAUSE (§1.4)** — `moveRel(0, 0)` timed with `PAUSE = 0.1` and `PAUSE = 0`. A
zero-delta move so nothing on the operator's desktop actually moves.

**Library availability (§1.5)** — `pip install --dry-run --no-deps` for each candidate, which
resolves a wheel without installing it, and one `curl` carrying `Upgrade: websocket` headers
through the tunnel to see whether aiohttp or Caddy answered.

No remote click, key or type was fired during this research — those would have landed on the
operator's live desktop.
