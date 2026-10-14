# DECISIONS

**Why the system is shaped the way it is.** Three sections, three id spaces:

| Section | Id | Holds |
|---|---|---|
| [Decided](#decided) | `D-nnn` | a non-obvious choice: what was chosen, what was rejected, how to reverse it |
| [Assumed](#assumed) | `A-nnn` | something taken as true without checking. `⚠️` marks the risky ones |
| [Blocked](#blocked) | `B-n` | something that needs a person, with the remedy and what was built instead |

**Append-only.** A changed mind is a **new** entry that says which one it supersedes; the old
entry stays exactly as written. History that gets edited stops being evidence.

**Ids are permanent and never reused.** Cite them (`D-nnn`) from code comments, commit bodies
and session chunks instead of restating the content.

**Allocate by reading the tail of the section**, immediately before you append.

`D-002`–`D-014` were **recovered on 2026-09-02** from the changelog, the code and its
comments, during the bootstrap. They are dated by the version that shipped them, not by the
day they were written down, and the provenance line says which. Everything in them is
traceable to a released change; nothing was invented to fill the template.

---

## Decided

## D-001 — The wiki lives in `docs/` and is tracked, except the topology file

**2026-09-02** · row 1 · `.gitignore` · [chunk](sessions/01-bootstrap/2026-09-02-wiki-bootstrap.md)

Documentation lived in `materials/`, which was in `.gitignore` — 31 files, 160KB of feature
chunks, none of it in git, none of it in a clone. It moved to `docs/` because every tool in
the kit reads `docs/`, and it came out of `.gitignore` at the same time, because a wiki that
does not travel with the repository is a wiki that only one machine has. One file stays
ignored: `imported/vps-architecture.md`, which maps the VPS, the VPN subnets and the
operator's other services, and this repository is public.

**The alternative rejected:** keeping `materials/` and pointing the kit at it. Every skill
would then need a special case, and the ones installed from the marketplace cannot be
special-cased at all — they read `docs/` by name. The other alternative, ignoring `docs/`
wholesale as `materials/` was, keeps the privacy but loses the reason to have done the move.

**Instruments:** `python -m pytest tests/ -q` → 94 passed, unchanged; the move touched no
code. `check-links.py` and `wiki-doctor.py` clean. 8 files had `materials/` paths rewritten.

**Reverse:** cheap and mechanical — `git mv docs materials`, restore the ignore line, revert
the path rewrites. The published history would remain published.

---

## D-002 — The singleton guard kills by API, in-process, and waits for real death

**2026-08-20** · shipped v0.18.0 · `utils/singleton.py`

A zombie instance held `:8080` through a **40-minute crash loop**. The cause was not the
lock: process *creation* on this box was hanging, so `taskkill /F` timed out at 10s and the
WMI enumeration at 20s on every restart — while an API-level kill of the same pid worked
instantly. The guard now enumerates and kills through psutil with zero child processes, and
waits up to 5s, because the port frees only when the process is really gone.

**The alternative rejected:** shelling out to `taskkill`, which is the obvious way and is
what failed. On a box where spawning a process is the slow operation, every fix that spawns
a process is the same bug.

**Instruments:** the incident itself — 40 minutes of crash loop, resolved on restart with
the new guard. psutil added to `requirements.txt`.

**Reverse:** revert the module; the interface it exposes is one function.

---

## D-003 — The tunnel targets a hostname, never a raw IP

**2026-08-09** · shipped v0.16.6 · `start_tunnel_vps.ps1`

The VPS address was pinned in the repository. It was silently dropped by RF DPI on
2026-08-07 and replaced, which made an infrastructure event into a code change. The keeper
now targets a name; the raw address survives only as a commented fallback for when DNS
itself is the broken thing.

**The alternative rejected:** keeping the IP and editing it on each migration — which is
what had just cost a commit. Also rejected: putting the name behind Cloudflare's proxy. That
proxy is HTTP-only and would break ssh exactly as it breaks the VPN's UDP, so the record
must stay DNS-only.

**Instruments:** after recovery, local frame 0.09s / 70KB, public 0.50s / 71KB ≈ 140KB/s.

**Reverse:** one line in the script.

---

## D-004 — The phone excludes the bot's host from its VPN, and the fix is routing, not code

**2026-08-06** · shipped v0.16.4 · [documentation/README-vps.md](documentation/README-vps.md)

The Mini App crawled on the phone and was instant on the PC. The bot's hostname resolves to
**the same VPS that hosts the operator's VPN**, so with the VPN on, the phone tunnelled bot
traffic to the VPS *through* the VPS. The PC is immune because WireGuard auto-excludes its
own endpoint address from the tunnel; Android WireGuard protects only its own socket, so
application traffic to that address still enters it. The fix is a split-tunnel exclusion on
the phone. Amnezia excludes by **address, not hostname**, so the exclusion does not follow
DNS and must be re-checked after every migration — which is the trap that made this recur.

**The alternative rejected:** treating it as a performance bug in the frame path, which is
where three days went first. Ruled out by measurement in this order: server (40ms/frame),
PC→VPS link (46 Mbit/s), VPS shaping (`tc`: none), hairpin/DNS/NAT (the VPN container
fetches the dashboard fine), MTU (client 1280 changed nothing; the interface MTU is a
correct 1420).

**Instruments:** the signature was a **draining budget**, not a size cliff — frames start at
2–3s and degrade to 17–18s within one session while `/api/click` stays instant. Frame abort
was raised 20s → 45s as a consequence: over a policed link a frame legitimately takes ~18s,
and aborting throws away bytes already transferred.

**Reverse:** nothing in the repository to revert; it is a setting on a phone.

---

## D-005 — `type_and_enter()` is the only place that sequences paste-then-Enter

**2026-08-17** · shipped v0.17.0 · `handlers/input.py`

Every typing path pasted and then pressed Enter **0.1s later**. Claude Code detects a
bracketed paste and buffers the block; an Enter arriving inside that window is folded into
the paste as a literal newline instead of submitting. The message sat in the input box while
the bot answered `Typed: …` — on all five surfaces at once, which is why it read as random.
`TYPE_ENTER_DELAY` (0.45s) is the gap, and no caller presses its own Enter.

**The alternative rejected:** raising the delay at each call site. Five copies of a timing
constant is five places for the next person to fix four of. A test now fails if any path
pairs `_type_text` with its own Enter.

**Instruments:** a new log line caught the real behaviour — two `Test` messages arrived glued
as `TestTest` (first Enter eaten, second submitted both) while a third went through.
`/api/paste` keeps bare `_type_text` on purpose: it types an image path and sends no Enter.

**Reverse:** the constant is env-tunable; the single-sequencer rule is not worth reversing.

---

## D-006 — The paste key is chosen from the target window

**2026-08-17** · shipped v0.17.1 · `handlers/input.py` → `paste_hotkey_for()`

Typing was still silent after `D-005`. **Claude Code binds `Ctrl+V` to "paste image from
clipboard"**, so a text paste is a no-op: the keystroke arrives, the clipboard is right, the
prompt stays empty. Terminal-ish targets now get `Ctrl+Shift+V`; ordinary apps keep `Ctrl+V`,
which is what Notepad and browsers actually honour.

**The alternative rejected:** sending `Ctrl+Shift+V` everywhere. It is not a paste in most
applications, so that trades a broken terminal for a broken everything-else.

**Instruments:** isolated against the live window rather than guessed. Elevation ruled out
(all three VS Code windows are one non-elevated pid). Focus verified. Clipboard verified
(310 chars readable). Key delivery verified — `Ctrl+Shift+P` opened the command palette. Then
`pyautogui.write` produced `> TYPED-999` while `Ctrl+V` produced nothing; `Ctrl+Shift+V`
produced `> CSV-111`, `Shift+Insert` nothing. Confirmed in a second terminal.

**Reverse:** `TYPE_PASTE_HOTKEY` / `TYPE_TERMINAL_PASTE_HOTKEY` / `TYPE_TERMINAL_HINTS` are
all env-tunable.

---

## D-007 — Terminal-ness is decided by the process, and only then by the title

**2026-09-01** · unreleased (v0.21.0 in the working tree) · `config.py` → `TYPE_TERMINAL_PROCS`

`D-006` matched on the window title, and a terminal renames itself to whatever runs inside
it. `WindowsTerminal.exe` showing `✳ Claude Code` matched no hint in the list, took the
`Ctrl+V` branch, and the silent no-op came back for a surface that had never been tested.
The executable does not change when the program inside it does, so the process name is the
real test; the title list stays as a fallback.

**The alternative rejected:** adding `claude code` to the title hints and stopping there. It
was added — and it fixes exactly this one program's window title, until the next program
renames a terminal.

**Instruments:** covered by the v0.21.0 tests, 74 → 94 overall.

**Reverse:** `TYPE_TERMINAL_PROCS` is env-tunable and empty means "title rules only".

---

## D-008 — The VS Code terminal-focus sequence exists in exactly one file

**2026-08-25** · shipped v0.20.0 · `utils/vscode.py`

`focus_window_exact` raises the **window**; the keyboard focus inside it does not move, and
after `code -n` that is the editor — where `Ctrl+Shift+V` is an editor binding and the paste
vanishes. The command-palette sequence that fixes it already existed as a private function
in `utils/scheduler.py`; it was deleted there and imported from one shared module.
`focus_terminal_if_active()` returns `(focused, message)` and `/api/type` renders a non-VS-Code
foreground as a loud red toast rather than a cheerful `Typed:`. **The text is typed either
way** — a wrong guess about the foreground window must not eat it.

**The alternative rejected:** letting each caller keep its own copy. `test_terminal_focus_lives_in_one_place`
fails if a second one appears, because a divergent copy is precisely how one surface
silently goes back to typing into the editor.

**Instruments:** tests 68 → 74 at v0.20.0.

**Reverse:** the module is one import; the test is the thing worth keeping.

---

## D-009 — A window is identified by the tail of its title, not by a prefix

**2026-08-16** · shipped v0.16.7 · `utils/window.py` → `tail_key()`

VS Code puts the open file **first**: `config.py - Tg-IDE-bot - Visual Studio Code` and
`index.html - Tg-IDE-bot - Visual Studio Code` share no prefix and neither contains the
other, so the existing rules declared the chip dead. `tail_key()` — the last two `" - "`
segments, lowercased — is a fourth rule on both the server and the client. Empty for
single-segment titles, which must never match.

**The alternative rejected:** one matcher for everything. There are deliberately two:
`_sameWin` (exact → containment → prefix → tail) answers *"will focus find it?"* and mirrors
the server; `_sameWinId` (exact → tail) answers *"is this the same window?"* and drives
dedupe and highlighting. Containment is too loose for identity — "Telegram" is inside
"Telegram Web - Google Chrome".

**Instruments:** `test_recent_validation_mirrors_server_matching` fails if the two sides
drift apart.

**Reverse:** removing the rule brings back a chip that silently matches nothing.

---

## D-010 — `/refine` is isolated by a server-enforced scoped token, not by markup

**2026-08-24** · shipped v0.19.0 · `utils/webauth.py`, `handlers/web.py`

The refinement view has no Type button, because typing into a focused window is remote
control and Copy is not. That is a UI claim, so it is backed by a server one:
`POST /api/scope` mints a 12h `refine.<exp>.<hmac>` bearer, and `_check_auth_refine()` is
called by exactly three handlers while the other 24 reject it with 401. The scope is
**inside** the MAC — signing the expiry alone would let anyone rewrite the prefix — the key
is derived so it shares no material with the `initData` check, and it is read from the
`Authorization` header only, never `?token=`, which lands in every proxy log.

**The alternative rejected:** a `refine_ok=` keyword argument on the shared checker. A second
function means the system handlers get a zero-line diff, and a bad merge that drops it fails
**closed** instead of quietly opening a shell route.

**Instruments:** `test_scoped_token_rejected_by_system_routes` and
`test_every_api_handler_checks_auth` pin both the behaviour and the count of three.

**Honest limit, and it is written into the chunk too:** inside the Telegram webview
`Telegram.WebApp.initData` is readable by any script and *is* a full credential, and
`localStorage` is same-origin state. No page can fence either off. What the scope buys is
defence against this page's own code, a CI-tested "no typing to the PC" invariant, a
genuinely narrowed browser flow, and hours-not-forever blast radius on a leak.

**Reverse:** deleting the second checker re-opens every route to the scoped token. Do not.

---

## D-011 — One request in flight, chained from completion, never a timer

**2026-08-05** · shipped v0.16.1, extended v0.16.3–v0.16.4 · `web/index.html`

Everything reaches the phone through a **single reverse-SSH pipe**. Blind post-click
refreshes at +500ms and +1600ms stacked on top of auto ticks; the queue grew unbounded and
late frames were dropped, which presented as "a click takes 15 seconds". The client now
keeps one capture in flight, collapses extras into one pending run, and chains the next from
the previous one's *completion*.

**The alternative rejected:** `setInterval`. On a pipe with variable latency a fixed interval
is a guarantee of pile-up. The same reasoning later applied to the scroll-arrow hold-repeat,
which chains for the same reason.

**Instruments:** 250KB → ~40KB per frame; 0.44s through the tunnel, click round trip 0.37s.
Then WebP + binary transport (v0.16.3) took a 1280px frame 109KB → 50KB, and 1920px to 82KB
— less than the old 1280px cost, so resolution went **up** while bytes went down. A hidden
tab was pulling 1.2GB/day before it learned to pause.

**Reverse:** the loop is one function; reverting it reintroduces a measured 15s regression.

---

## D-012 — Typing goes out as virtual-key codes, because the layout silently ate it

**2026-09-01** · unreleased (v0.21.0 in the working tree) · `utils/layout.py`

`pyautogui` resolves a character through the **active** keyboard layout. Under a Russian
layout `VkKeyScanW('v')` returns `-1` and the key is simply never sent — so every typing
path broke, invisibly, based on a setting in the target window that a phone cannot see.
Typing no longer depends on the layout; the operator still needs to *know* it, so the layout
is readable and switchable over the API.

**The alternative rejected:** forcing the layout to English before typing and back after. It
changes the operator's machine as a side effect of sending a message, and it loses whenever
the switch does not take before the keystroke.

**Instruments:** part of the 74 → 94 test growth.

**Reverse:** the module is self-contained; the virtual-key path is not worth reversing.

---

## D-013 — The humanize model has a fallback chain and fails loudly

**2026-08-17** · shipped v0.17.1 · `utils/humanize.py`

Groq retired `llama-3.3-70b-versatile` mid-day — normal at 13:18, `404 does not exist or you
do not have access` by 14:25, the whole Llama family gone from the key. Whisper was
untouched, so recognition kept working and only the cleanup died. The first model that
answers now wins and the switch is logged, so the next retirement costs quality rather than
the feature. And a failed cleanup is a **red toast** carrying the raw text, not a log line:
the old behaviour returned the transcript with a warning nobody saw, which is
indistinguishable from "the AI button does nothing".

**The alternative rejected:** pinning one model. That is what broke. Also rejected:
`gpt-oss-20b` as primary — on a mixed RU/EN dictation qwen3.6 was faster (0.46s vs 0.61s) and
kept the speaker's self-correction.

**Instruments:** `HUMANIZE_REASONING=none` plus defensive `<think>…</think>` stripping,
because unguarded, qwen3.6 returned **7196 chars of chain-of-thought** for a 483-char
transcript — which would have been typed into a terminal verbatim.

**Reverse:** both the model and the chain are env-tunable.

---

## D-014 — In the Improve prompt, the profile goes first and the instructions last

**2026-08-20** · shipped v0.18.0 · `utils/improve.py`

Measured against live qwen3.6-27b, and locked into the chunk so it is not undone. With the
operator profile placed *after* the style rules, the model copied `principles.md` verbatim
into its output as a fake "Constraints" section. Profile first, instructions last.

**The alternative rejected:** trusting an instruction to hold the output language. It does
not: no instruction survives a 6KB English persona dragging Russian input into English. The
fix is deterministic — `_lang_hint()` counts Cyrillic, and >50% appends "Output language:
Russian" **last**, skipped for translate.

**Instruments:** both behaviours observed against the live model before the order was fixed.

**Reverse:** reordering the prompt reproduces both failures; that is what makes it a
decision rather than a preference.

---

## D-015 — The file caps were raised to what the code actually is, and the breaches named

**2026-09-02** · row 1 · `.claude/rules/file-limits.md` · [chunk](sessions/01-bootstrap/2026-09-02-wiki-bootstrap.md)

The historical caps — handler 150, utils 100, `bot.py` 100, `config.py` 50 — were written at
v0.1.0 and had been silently untrue for months: `handlers/web.py` is 605 lines, `config.py`
152. A cap nobody believes is not enforcement, it is noise, and `tools/wiki/hook_caps.py`
now reads that table on every edit, so noise would have arrived on every edit. The numbers
are set to what a file of each kind honestly is (handler 200, utils 150, entry point 120,
config 160), and the two handlers that still exceed them are named in the rule itself and on
the board as [row 5](ROADMAP.md).

**The alternative rejected:** keeping 150 and treating the warnings as background. That is
how the old caps died — a limit that fires constantly stops being read, and then it cannot
tell you about the file that has genuinely gone wrong. Also rejected: raising the cap to 605
so nothing is in breach, which converts a real smell into a permanent lie.

**Instruments:** line counts on 2026-09-02, listed in
[code-map.md](code-map.md). The hook warns, never blocks — whether a file has taken on a
second job is a judgement, and the hook is not the one making it.

**Reverse:** edit the table; it is four rows and one file reads it.

---

## D-016 — The scroll pads are styled against the screenshot, not the page theme

**2026-09-02** · row 8 · `web/index.html` · [chunk](sessions/02-mobile-compaction-visible-scroll-arrows-foldable/2026-09-02-mobile-compaction-visible-scroll-arrows-foldable.md)

The ▲▼ pads float **over the captured screenshot**, so the page's light/dark setting says
nothing about the pixels behind them — those are whatever the remote window happens to be
showing. Every colour in `.scroll-pad button` is therefore a literal, and the thing that makes
the control readable on any backdrop is a light hairline ring
(`border:1px solid rgba(255,255,255,.55)`) plus a shadow, with the fill raised `.42` → `.78`.
Reported as "I don't see arrows up and down there"; they had been rendering all along.

**The alternative rejected:** a theme-aware fill — light pill in light mode, dark in dark.
It keys on the wrong variable: the operator can be in light theme looking at a black terminal,
or dark theme looking at a white document, and the fill would be exactly wrong in both. It
would also split the viewer's palette, since `.scroll-pad` is shared with `#lb-scroll` and
`#lb-zoom`, where every other control is a translucent pill on dark. Also rejected: a second,
non-overlaying pair in `.screen-head` — that row already wraps to two lines at 360px, so it
would cost a permanent row of screenshot to work around a contrast bug, and `KEYS` already
carries `Up`/`Down`, which send *keyboard* arrows and would sit beside a wheel pair looking
identical (the Tab/Sh+Tab scar).

**Instruments:** the cause was narrowed by elimination against the live system, not guessed —
no media query touches the pad, no JS hides it, it is not clipped, and the access log proved
the phone was running the **current** client (it calls `/api/layout`, which exists only there),
which killed the stale-cache hypothesis. Tests 94, with 12 new assertions mutation-tested:
eight deliberate reverts, eight failures.

**Two bugs fixed inside the same six lines**, neither of them reported: `:active`/`.on` was
`var(--accent)`, which in night theme is `#ece9e4` against `color:#fff` — the held state of a
hold-to-scroll was **white on white**, so the one control whose whole interaction is "press and
keep pressing" had no dark-mode feedback at all. And `:hover` was the only rule that raised the
contrast, which on a touch device is no rule at all.

**Reverse:** six CSS lines. The ring is the load-bearing part; dropping it restores the
invisible control, and a test now fails if it goes.

---

## D-017 — Right click is a two-finger tap, and the double tap keeps both jobs it already had

**2026-09-07** · row 11 · `web/index.html` · [chunk](sessions/04-route-a-right-click-drag/2026-09-07-route-a-right-click-drag.md)

The operator asked for a right click and named the gesture: two fingers, the trackpad
convention. It is also what Moonlight and the Microsoft RD client use in pointer mode. On the
live view and in the zoomed viewer, two fingers down, neither moving past `TAP_MOVE_PX`,
released inside `RIGHT_TAP_MS` (400ms), sends `button: "right"` anchored at the midpoint of
where the fingers **landed** — not where they were at release, which has drifted.

**The alternatives rejected.** *Double tap*, which the brief first asked for: it is spent
twice already — on the remote double click (a 280ms tap-delay upgrade) and, in the viewer, on
fit↔3× zoom. Taking it would have removed a verb to add a verb. *Long press*, which is the
common default: on every client that ships it, it is the gesture users report as "the PC
thinks the left button is held down"; it is also now the drag arming gesture here, where a
held button is what is actually meant.

**Why it did not already work.** `_lb.multi` was set on the second `pointerdown` and
`pointerup` returned early on it — deliberately, so the tail of a pinch could not be read as a
tap and close the viewer. And the two-pointer branch of `pointermove` set `moved = true` on the
first pixel of movement, which two fingers landing together always produce. So the gesture was
not missing, it was **suppressed twice over**. The fix splits the meaning: `multi` still stops
a pinch closing the viewer, `peak` counts fingers, and movement now needs the pinch *span* to
change by more than `TAP_MOVE_PX`. On the un-zoomed image the browser still synthesises a
click from the first finger, so it is suppressed for 400ms — otherwise a right click also
sends a left one.

**Reverse:** delete the `peak === 2` branch in the viewer's `pointerup` and the pointer
handlers in `bindImgClick`; nothing else depends on them.

---

## D-018 — A drag is one request, and the button is released in a `finally`

**2026-09-07** · row 11 · `handlers/web.py`, `utils/mouse.py` · [chunk](sessions/04-route-a-right-click-drag/2026-09-07-route-a-right-click-drag.md)

`POST /api/drag {x, y, to_x, to_y, button}` presses, interpolates the move in
`MOUSE_DRAG_STEPS` steps and releases — all inside one request.

**The alternative rejected:** `/api/mouse {down|up|move}`, which is what a real remote-control
protocol does (RustDesk packs exactly that into one `MouseEvent.mask`). It is the right shape
for a socket and the wrong shape for this transport. A button held *between* HTTP requests is
a button the tunnel can strand: lose the `up` — a dropped connection, a backgrounded webview,
a phone that locks mid-gesture — and the operator's desktop is left with the mouse down, where
every movement is a selection, and nothing on the phone can tell them so. One request cannot
be half-delivered, and `utils.mouse.drag` releases in a `finally` even when a move raises.

The move is interpolated because a single jump from A to B drags nothing: controls recognise a
drag from the stream of `WM_MOUSEMOVE` between the press and the release. `MOUSE_DRAG_HOLD`
sits between the press and the first move for the same reason — an app that sees both in one
tick treats it as a click.

**Reverse:** the endpoint is additive; removing it removes the gesture and nothing else.

---

## D-019 — pyautogui's blanket PAUSE is off, and every gap it hid is now named

**2026-09-07** · row 11 · `handlers/input.py`, `utils/mouse.py`, `config.py` · [chunk](sessions/04-route-a-right-click-drag/2026-09-07-route-a-right-click-drag.md)

`pyautogui.PAUSE` sleeps 0.1s after **every** call it owns — measured on this machine at
100.5ms against 0.1ms with it off. `pyautogui.click(x, y)` is a move and a click, so every
remote click spent ~200ms asleep before an event was sent, `scroll_at` ~300ms, and a drag would
have spent ~400ms — on top of a ~133ms warm tunnel round trip. It is now `0`, set beside
`FAILSAFE` in `handlers/input.py`, the module every entry point already imports.

**What the blanket delay was paying for is now explicit** in `config.py` and spent in
`utils/mouse.py`: `MOUSE_MOVE_SETTLE` before a button goes down (a window must process
`WM_MOUSEMOVE` first, or the click lands on a control that has not registered the hover) and
before the wheel (Windows routes it by cursor position at the moment of injection —
**this one was a live regression the moment PAUSE went to zero**, and it is why `scroll_at`
now sleeps explicitly). The keyboard paths never needed it: `press_keys` has always sent its
virtual-key events back-to-back.

Because a caller that reaches for `pyautogui.click` directly skips all of it, every mouse
event now goes through `utils/mouse.py` and `test_every_click_path_uses_the_mouse_module`
fails if a second path appears — the same shape as `D-005`'s sequencer rule and `D-008`'s
single-copy rule, and for the same reason: the symptom of skipping it (a menu that opens on
the second try) never points back at the cause.

**Reverse:** one line, `pyautogui.PAUSE = 0.1`. The explicit settles are harmless if it comes
back — they would simply be paid twice.

---

## D-020 — A hold is a right click, and the same hold becomes a drag only if the finger moves

**2026-09-07** · row 11 · `web/index.html` · **supersedes the long-press rejection in `D-017`**
· [chunk](sessions/04-route-a-right-click-drag/2026-09-07-route-a-right-click-drag.md)

`D-017` chose the two-finger tap and rejected the long press, citing clients where it misfires
as a held left button. The operator's correction is simply true: **holding is the right click
people arrive expecting** — it is what Android does, what Microsoft's RD client does in
direct-touch mode, and what a hand reaches for before it thinks. A gesture the user already
knows beats a gesture that is defensible.

The cited failure does not apply here and it is worth saying why: it describes clients that
implement the hold by *holding the remote left button down* and hoping the target interprets
it. This sends a discrete `button: "right"` click. Nothing is held anywhere.

**The collision, and how it is resolved.** The hold was already taken — it arms the drag. One
gesture cannot mean two things at the moment it is recognised, but it can mean two things
depending on **what happens next**:

| after the hold is recognised (350ms) | sends |
|---|---|
| released in place | right click at the anchor |
| moved past `DRAG_MOVE_PX` (16px), then released | drag from anchor to release point |

`DRAG_MOVE_PX` is deliberately coarser than `TAP_MOVE_PX` (8px): a finger resting on glass for
350ms always drifts, and a right click that drifts into a 16px drag is how a context menu
becomes a moved file. The status line names the fork the moment the hold lands
(`Hold — release for right click, move to drag`), so the two outcomes are discoverable rather
than remembered.

**The live view keeps only half of it.** There is no drag there — a finger moving on that
image scrolls the *page*, which cannot be given up — so the hold has exactly one meaning.
Which also means the surfaces do not disagree: a hold released in place is a right click on
both.

**Two-finger tap stays** (`D-017`). It is faster, it needs no wait, and it is the trackpad
gesture; the hold is the one that needs no explanation. Neither is a mode.

**The OS gets there first unless it is stopped.** A long press on an `<img>` opens the
platform's own "save image" sheet, which both answers the gesture and cancels the pointer
sequence. `-webkit-touch-callout:none` plus a `contextmenu` preventDefault (only while Click
is armed) is what leaves the hold to us.

**Reverse:** drop the `!dragging` branch in the viewer's armed-hold release and the
`holdTimer` in `bindImgClick`; the two-finger tap keeps working on its own.

---

## D-021 — Four controls never fold, everything else does, on both phone surfaces

**2026-09-07** · row 15 · `web/index.html` · [chunk](sessions/05-mobile-control-grouping/2026-09-07-mobile-control-grouping.md)

The zoomed viewer showed four full-width rows over the screenshot on a phone, one of them
(`#lb-view-row`) carrying two pills — the layout and Auto — while the row above it wrapped for
want of space. The bottom bar squeezed its freeform field to **84px** to keep nine keys and a
trail on the same line. Both are the same mistake: everything was treated as equally worth a
permanent pixel.

**What stays out, on both surfaces:** the **text field**, the **layout pill**, the **attach
clip**, and — in the viewer — **Click**. Those are what the operator touches between two typed
answers. Click is on the list because it is the switch that makes a tap reach the PC at all
(`D-017`, `D-020`); folding it away would hide the master switch for every gesture in the app.
The clip is *added* to both surfaces here — it existed only in the viewer's key row and in the
dashboard's Type panel, neither of which is reachable while looking at a screenshot.

**What folds:** windows, projects, Claude, the interval, Auto, and the arrow/Enter/Tab strip.
Auto moved in beside the interval it sets, which is what removes the one-pill row.

**The fold is the third user of one idiom, not a third invention.** A class on the container,
a caret from a `::after` pseudo-element, one key in the `acc_` localStorage namespace — the
same as `.panel.acc` and the quick-keys bar. The viewer's default differs by screen rather than
by preference: folded where the compact breakpoint matches (the rows cost picture there), open
on a desktop viewer that has room; a stored choice beats both.

**The bar's fold changed meaning, deliberately.** It used to hide everything and leave a ~24px
sliver, with the body clearance shrinking to match. It now hides only the key strip and the
trail. On a phone that strip scrolls horizontally, so it never cost height — it cost the
**width** that left the field at 84px. Folded, the field takes the whole bar. The consequence
is that clearance no longer depends on the state, and the two `62px` literals are again the
whole story; the `body.qk-hidden{padding-bottom:26px}` override is gone and a test fails if it
returns.

**The alternative rejected:** keeping the sliver and adding a *second* always-on strip above
it. That is two bars where the phone has room for one, and it would have put the field further
from the thumb than the keys it exists to replace.

**Reverse:** delete `#lb-more`/`#lb-quick`/`#lb-entry` and put the rows back in `#lb-bottom`;
move `#lay-btn` back inside `.qk-btns`. Nothing else depends on the grouping.

---

## D-022 — The digits come back beside the freeform field, not instead of it

**2026-09-07** · row 15 · `web/index.html` · **partially supersedes v0.20.0's removal of the
digit buttons** · [chunk](sessions/05-mobile-control-grouping/2026-09-07-mobile-control-grouping.md)

v0.20.0 replaced the fixed `1` / `2` buttons with one freeform field, on the argument that the
two taps those buttons covered still worked by typing them while everything they could not
answer now worked too. True, and the field stays. What the argument missed is what typing
costs on a phone: the on-screen keyboard opens over the screenshot you are answering *about*,
for a single character.

So `1` and `2` are back on both phone surfaces, beside the field rather than in place of it —
one tap for the common case, the field for everything else. `2` is tinted green in all three
places it now appears, because a control that means one thing should not change colour
depending on which bar it is in.

**Vertical arrows join them in the viewer.** They were bottom-bar-only, deliberately: four
arrows cost width over the picture. That argument expired when `D-021` moved the viewer's key
row inside the fold — the width is only spent while the group is open, and until now a phone
answering a numbered prompt from the zoomed screenshot could not move Claude Code's selector
at all.

**Reverse:** delete the four buttons from `#lb-keys` and the two from `.qk-btns`; nothing
depends on them.

---

## D-023 — On the live view the hold fires at 350ms, not on release

**2026-09-08** · row 16 · `web/index.html` · **supersedes the release-decides half of `D-020` for the live view only** · [chunk](sessions/06-hold-never-fired/2026-09-08-hold-never-fired.md)

`D-020` made a hold mean two things, resolved by what the finger does next: released in
place it is a right click, moved past `DRAG_MOVE_PX` it is a drag. It shipped and **never
fired once**. The log is unambiguous — 31 clicks in a live session, every one `left`, not a
single `button: right` request in the server's whole history.

**Three causes, all of them "the gesture was cancelled before it could be recognised":**

1. The hold was cancelled by the **tap** threshold — `TAP_MOVE_PX` (8px from the landing
   point) on the live view, and the **3px pan** threshold in the viewer. A finger resting on
   glass for 350ms clears both every time. A hold now has its own `HOLD_SLOP_PX` (14px),
   measured from where the finger landed rather than per move event, so accumulated drift is
   what counts and not one jumpy sample.
2. **The webview claims the gesture.** With the default `touch-action`, a resting finger on
   the live image is a possible page scroll, and the browser answers with `pointercancel` —
   no error anywhere, and no `pointerup` to complete on. While Click is armed the image is a
   control surface and gets `touch-action: none`; the viewer already had it.
3. **The completion depended on `pointerup` reaching the same element.** Without pointer
   capture a finger that drifts off the image releases somewhere else. `setPointerCapture` on
   pointerdown fixes that, but the deeper fix is not to need the release at all.

**So on the live view the right click is sent by the timer**, at the moment the hold is
recognised, anchored at the landing point — with the haptic arriving while the finger is
still down, which is what every OS long press does and what makes the gesture feel answered.
The release only swallows the synthetic click that follows.

**The viewer keeps arm-then-decide**, deliberately: a drag lives there and its target is
where the finger *ends up*, so that gesture genuinely cannot be resolved until the release.
The asymmetry is not an inconsistency — the live view has no drag, so a hold there has
exactly one meaning and nothing to wait for.

**What this does not change:** the two-finger tap (`D-017`), which never depended on any of
it, and the viewer's drag (`D-018`).

**Reverse:** move the `_fireClick(..., 'right')` call out of the timer and back behind
`wasHold` in the release handler.

---

## D-024 — The two-finger tap is the right click, and it was unfireable for the same reason the hold was

**2026-09-08** · row 20 · `web/index.html` · **makes `D-017`'s gesture the primary one** · [chunk](sessions/06-hold-never-fired/2026-09-08-hold-never-fired.md)

The operator's ruling: right click is the **short two-finger tap**, the trackpad convention.
`D-017` chose that gesture and it has never fired — the server log shows **zero** `button:right`
requests in its whole history, from either gesture.

The cause is the one `D-023` found for the hold, in a second place: the tap was gated on
`TAP_MOVE_PX` (8 px from each finger's landing point) on the live view, and on an 8 px change of
the **pinch span** in the viewer. **Two fingers landing together always drift more than 8 px
between them.** So the gate that distinguishes a tap from a drag also made the two-finger tap
impossible, exactly as it made the hold impossible. Both now use `HOLD_SLOP_PX` (14 px); the
400 ms window is unchanged, because "short" is the point.

**The long press stays on the live view** (`D-023`) as a second route to the same verb. It costs
nothing, it is what a hand reaches for on a touchscreen, and the two paths cannot collide — the
hold timer requires exactly one pointer. If it ever misfires on a resting finger it comes out in
one line, and the two-finger tap is unaffected.

**Reverse:** put `TAP_MOVE_PX` back in the two gates. The measurement that says not to is in
`D-023`.

---

## D-025 — Characters and named keys are two paths that never merge, and both doors enforce it

**2026-09-09** · row 17 · `handlers/input.py`, `web/index.html` · **implements a row-10 constraint** · [chunk](sessions/08-direct-typing/2026-09-09-direct-typing.md)

A `KEYEVENTF_UNICODE` key carries **no virtual-key code**. A synthetic Ctrl therefore has
nothing to combine with, and a helper taking "a string, possibly with modifiers" is the bug
waiting to be written. So `type_unicode()` carries characters and `press_keys()` carries every
named key and combo, and neither calls the other.

The rule is enforced at both doors rather than trusted to callers. `type_unicode()` **refuses
every control character by name** — Enter most of all, because Enter is sequenced against a
paste by exactly one function (`D-005`) and a Tab or an Escape arriving through a text field is
a keystroke the client never meant to send. The client honours the same split: `beforeinput`'s
`insertLineBreak` and `deleteContentBackward` become named keys through `/api/key`, never
characters.

**The Win32 detail that costs a session to rediscover:** `sizeof(INPUT)` must be **40** on x64,
because the union's largest member is `MOUSEINPUT` (32 bytes). Declare the union with
`KEYBDINPUT` alone and it is 32, whereupon Windows rejects **every** call with
`ERROR_INVALID_PARAMETER` (87) and sends nothing. Experiment E2 failed exactly this way before
it succeeded. `press_keys` never met it because it uses the legacy `keybd_event`.

**Reverse:** merge the two into one "type this, with modifiers" helper. The layout bug class
`D-012` fixed comes back on whichever surface forgets which path it is on.

---

## D-026 — A targeted send guards the foreground; it never re-focuses it

**2026-09-09** · row 17 · `handlers/web.py`, `utils/window.py` · **narrows `D-008`** · [chunk](sessions/08-direct-typing/2026-09-09-direct-typing.md)

`/api/chars` takes an optional `expect`: the window the caller **believes** it is typing into.
A mismatch refuses and types nothing. It does not focus, and that is the decision.

Measured, in E2 on 2026-09-08: `force_foreground()` verified the foreground and returned
`True` honestly — and **800 ms later a different window held it**, and 62 characters went into
an unrelated editor. Focusing before each batch would re-run that race on every batch, at
typing speed. A stream is not a wrong guess made once; it is a wrong guess repeated 50 times a
second.

Comparison is `same_window_id()`, the server-side twin of the client's `_sameWinId` (`D-009`):
exact title, or a **non-empty** shared tail key. Not `focus_window_exact`'s rule, which is
deliberately loose — it answers "will focusing find it?", and containment would wave through
"Telegram" against "Telegram Web - Google Chrome". And not bare `tail_key` either: that returns
`''` for a single-segment title, and `'' == ''` made the first version of this guard **inert
against `✳ Claude Code`**, the one target the feature exists for.

**Reverse:** focus before typing, as `/api/type` does. Row 19 is the same argument pointing the
other way — that route should adopt *this* rule, not the reverse.

---

## D-027 — The typing surface is a password field, and autocorrect is off on purpose

**2026-09-09** · row 17 · `web/index.html` · [chunk](sessions/08-direct-typing/2026-09-09-direct-typing.md)

The client's keystroke sink is `<input type="password">` inside a `<form>`, off-screen but
**focusable**. Both halves are load-bearing.

*Password*, because Chrome-for-Android ignores `autocomplete` and `spellcheck` on an ordinary
field — noVNC hits the same wall, and xterm.js's own maintainers propose exactly this blunt
fix. iOS autocorrect goes further and rewrites words that have **already been committed**,
arriving as `insertReplacementText`. Locally an editor just fixes itself; here the characters
are already inside a terminal on the PC, and a keystroke cannot be un-sent. The suggestion
layer is therefore defeated at the field rather than handled afterwards, because there is no
"afterwards" that can help.

*Focusable*, because `display:none` cannot take focus and raises no keyboard — the mode would
simply look dead. It is 1 px at 1 % opacity, and `font-size:16px` so iOS does not zoom the page
when it is focused.

Two limits stay honest rather than engineered away: plain characters land immediately, but a
word the keyboard is **predicting** lands only when committed (`compositionend` is the only
reliable sync point), and an autocorrect that slips through cannot be recalled.

**Reverse:** a normal text field or a textarea. The Android suggestion strip returns, and with
it corrections applied to a remote terminal.

---

## D-028 — The chain is the batcher; the coalescing window measured to zero

**2026-09-09** · row 17 · `web/index.html` · **supersedes the 60–80 ms estimate in the row-18 study** · [chunk](sessions/08-direct-typing/2026-09-09-direct-typing.md)

`TYPE_BATCH_MS` shipped at 70 ms on a reasonable argument: this transport is chained HTTPS
through a tunnel with a ~133 ms warm round trip, not a WebSocket to a local PTY, so one request
per character would load the single pipe `D-011` exists to protect. No terminal project
publishes a debounce window, so the number was labelled an engineering choice to be measured.

**Measured on the first device session** (Android, 25 characters): every request carried
**exactly one character**. The shortest gap between two thumb keystrokes was **143 ms**, the
median **367 ms** — nothing ever arrived inside a 70 ms window. The window coalesced nothing
and delayed everything by 70 ms.

What actually batches is the **chain**: keystrokes arriving while a request is in flight merge
into the next one, so batch size becomes a function of the link — one character when the tunnel
keeps up, a batch when it does not. That is the behaviour the window was approximating, and it
needs no constant. The constant stays named at `0` because it is the knob to turn if a faster
typist or a slower link ever needs one.

**Reverse:** raise it. The cost is that latency, paid on every character, buys coalescing only
above ~7 characters per second sustained — a rate the measurement did not see.

---

## D-029 — The typing sink is never empty, and named keys come only from `keydown`

**2026-09-09** · row 17 · `web/index.html` · **reverses the "no sentinel" call in `D-027`** · [chunk](sessions/08-direct-typing/2026-09-09-direct-typing.md)

Backspace did nothing from the phone, and the server log settled it before any code was read:
**`backspace` appears zero times in its whole history** while the mode was in use. So the
keystroke never left the client, exactly like `D-023` and `D-024`.

Two causes, and the second is the larger one.

**The sink shipped empty.** An empty field with the caret at 0 has nothing to delete, so
Backspace is a no-op the engine does not even report — no `beforeinput`, no `input`, no
request. The `deleteContentBackward` branch was correct and simply never ran, which is why the
suite stayed green over a dead key. The field now holds a **sentinel** with the caret at its
end. `D-027` explicitly declined this ("only if a specific keyboard proves to misfire"); one
has, and the reversal is what that clause was for. The sentinel never leaves the phone —
characters are taken from `e.data`, never from the field's value.

**`beforeinput` has no `inputType` for a named key.** Tab, Delete, the arrows, Home/End and
every Ctrl combo can *only* arrive as a `keydown`, and the handler's Backspace branch was a
comment and nothing else — so on a device with a hardware keyboard (an iPad) all of them were
silently dropped. `KB_NAMED_KEYS` maps them onto the `press_keys` path, which is `D-025`'s
split doing its job rather than an exception to it.

`preventDefault` on a mapped key is load-bearing: it suppresses the `input` event, so the
sentinel's length diff cannot infer the same keystroke a second time. Shift alone is **not**
treated as a modifier combo — it is how capitals are typed, and treating it as one turns every
capital letter into a keystroke instead of a character.

**Reverse:** empty the sink again. Backspace goes quiet on any engine that declines to report a
deletion it did not perform, and it goes quiet *silently*.

---

## Assumed

## A-001 — The phone's slow link is carrier policing of the sustained UDP flow ⚠️

**2026-08-06** · bites the frame path, and `D-004` rests on it

Everything measurable was ruled out — server, link, shaping, hairpin, DNS, NAT, MTU. What
remains is a **draining budget**: frames start at 2–3s and degrade to 17–18s within one
session while small requests stay instant. That is the shape of policing rather than a size
cliff, but it was never confirmed with the carrier, and "what is left after elimination" is
an inference, not a measurement.

**Falsified by:** the same phone on a different carrier's SIM, or on someone else's Wi-Fi,
sustaining >100KB/s through the tunnel for a full session.

## A-002 — The phone's throughput collapse is environmental, not a code regression ⚠️

**2026-08-05** · bites every judgement about live-view performance

On 2026-07-23 the phone pulled 17,358 frames at a 1.0s median gap, 194KB each — roughly
194KB/s. Two weeks later the same device, same Telegram family, same tunnel managed 20–40KB/s.
Nothing in the frame path changed between those dates, so the collapse is assumed external.

**Falsified by:** checking out the 2026-07-23 revision and reproducing the old throughput on
the same phone today. Nobody has done it.

## A-003 — Nothing else on this machine wants port 8080

**2026-07-21** · bites `utils/singleton.py`, which kills what holds the port

The guard identifies a stale bot by the port it holds. If another program takes `:8080`
first, the guard's remedy is aimed at the wrong process.

**Falsified by:** `netstat -ano | findstr :8080` naming a pid that is not python, on a boot
where the bot has not started yet.

---

## Blocked

## B-1 — The infrastructure topology is already public and cannot be un-published

**Blocked:** deciding what to do about it. `README.md` and `start_tunnel_vps.ps1` are tracked
in a **public** repository and name the tunnel hostname and both VPS addresses; commit
`e039070` (v0.16.6) carries the address change in its **commit message**. Git history keeps
all of it, so redaction now lowers the detail on `HEAD` and changes nothing about what has
been fetched, forked or indexed since 2026-07-21.

**Remedy:** a person has to choose. The options, in increasing cost:

```bash
gh repo edit magerash/Tg-IDE-bot --visibility private   # stops new exposure, not old forks
# or: rotate what is cheap to rotate — the VPS address, the tunnel port
# or: accept it, on the record, and stop treating the topology as secret
```

**Second instance, found 2026-09-03 while preparing the v0.21.0 commit:**
`.claude/settings.local.json` is **tracked** (since v0.16.7) and carries the reverse-tunnel
command verbatim — `ssh -N -R 18080:127.0.0.1:8080 … root@vpn.magerash.com` — plus `nslookup`
lines for both hostnames and absolute paths containing the operator's username. It is a
*local* settings file; the Claude Code convention is that `settings.local.json` is personal
and gitignored, and this one should never have been committed. Untracking it is a one-line
`git rm --cached` plus an ignore rule, but it does not un-publish anything, so it is folded
into this blocker rather than done unilaterally.

**Built instead:** `docs/imported/vps-architecture.md` — the file with the VPN subnets,
the container names and the operator's other services — stays gitignored (`D-001`), with
[documentation/README-vps.md](documentation/README-vps.md) as the tracked stub. That stops
the exposure growing.

**Honest assessment:** worth an hour of the operator's attention, once. The bot's whole
purpose is remote keyboard and shell access to a personal PC, so the host that fronts it is
the interesting target, and it is currently named in a public README next to the port. The
mitigating fact is that no credential was ever published — the worst literal string in the
docs is the placeholder `YOUR_TELEGRAM_BOT_TOKEN`.

## B-2 — Process creation on this box hangs, and two subsystems work around it separately

**Blocked:** the root cause. `taskkill` timing out at 10s and a WMI enumeration at 20s
(`D-002`), and the tunnel watchdog's `tasklist` timing out after 15s every 75s, are the same
symptom in two places: **spawning a process is sometimes the slow operation on this machine.**
Nobody has found why — antivirus, a filter driver and disk pressure are all candidates and
none has been tested.

**Remedy:** a person with the machine, an afternoon, and Process Monitor.

**Built instead:** both call sites avoid spawning. The singleton guard enumerates and kills
in-process through psutil; the watchdog is on a long interval and tolerates its own timeout.
Neither is a fix.

**Honest assessment:** the workarounds hold, and it has not cost anything since v0.18.0. It
matters because it will hit a third call site eventually, and the third one will look like a
brand-new bug.

---

## D-030 — The LLM budget is always sent, sized from the input, and a truncated reply is refused

**2026-09-13** · row 22 · `utils/humanize.py`, `config.py` · [chunk](sessions/09-humanize-token-budget/2026-09-13-humanize-token-budget.md)

Groq checks a request's **expected** output against a per-model, per-org output-tokens-per-
minute cap *before* running it. With `max_tokens` unset the expectation is the model default,
2048; this org's cap on qwen3.6-27b is 1000. So every request 429'd without reaching the
model, and what the operator saw was the fallback's own failure: gpt-oss-20b answers 400 to
the `reasoning_effort=none` that qwen needs, and at its default effort it spent the whole
budget thinking about the twin persona and returned an empty content.

Three rules. `max_tokens` is always sent — `len(text) + 256`, capped at `HUMANIZE_MAX_TOKENS`
(900), under the measured limit. The reasoning effort is chosen **per model prefix**, because
one value cannot serve two model families that reject each other's. And `finish_reason=length`
**raises**: the chain moves on or fails loudly, it never returns the fragment.

**The alternative rejected:** returning the truncated text with a warning — the result is
typed into a terminal on the PC and the phone cannot see the cut. Also rejected: a larger cap
for the fallback model only. One cap, one instrument; a dictation that needs more output than
the cap fails on both models *by name*, which is a limit written down rather than a silent one.

**Instruments:** live probe 2026-09-13 — qwen without `max_tokens` → `429 … Requested 2048`;
with 700 → 200 in 1.28s. gpt-oss-20b with `none` → `400 must be one of low, medium, or high`;
with `low` → 200 in 0.49s. `tests/test_llm.py`, five mutations red.

**Reverse:** both are env — `HUMANIZE_MAX_TOKENS`, `HUMANIZE_REASONING`. Raise the cap past
1000 and the first request 429s again.

## D-031 — A successful click re-targets Keyboard mode; only an unasked foreground change is refused

**2026-09-29** · rows 23, 24 · `web/index.html` (`doClick`, `_mapToScreen`), `handlers/web.py` (`api_click`) · [chunk](sessions/10-typing-from-web-click-re-targets-keyboard-null/2026-09-29-typing-from-web-click-re-targets-keyboard-null.md)

`D-026` locks Keyboard mode to the window its first batch landed in and refuses any batch
whose foreground differs. On a desktop that also refuses the operator: they click a second
window on purpose, type, and the guard reads it as a focus thief, refuses, and switches the
mode off — `bot.log` 2026-09-28 17:32:36, `expected 'Жан', foreground is 'Вера'`. A click the
PC confirmed (`r.ok`) is the operator choosing a target, so it clears `_kbExpect` and the next
batch learns the new one. A window that takes the foreground **without** a click is still
refused, which is the case `D-026` was written for.

**The alternative rejected:** re-learning on every foreground change — that is the guard
removed. Also rejected: re-learning on the refusal toast — the operator would have to type
twice to be believed, and the first attempt is exactly the keystroke that went nowhere.

**Instruments:** `tests/test_input.py::test_a_click_re_targets_keyboard_mode`; the reset and
the guard were each deleted in turn, both red. Not yet confirmed on hardware.

**Reverse:** delete the `if (r.ok) _kbExpect = ''` line in `doClick`.

## D-032 — Changelog entries are headed `### vX.Y.Z date`, the kit's form

**2026-09-29** · row 26 · `docs/changelog.md`, `tools/wiki/hook_gate.py` · [chunk](sessions/11-kit-upgrade-v0-3-2/2026-09-29-kit-upgrade-v0-3-2.md)

Kit v0.2.0's commit gate denies a commit whose subject names a version that is neither the
changelog's `Open:` version nor a released one, and it reads the released ones from headings
matching `### vX.Y.Z`. This changelog wrote `### Changelog vX.Y.Z` for 48 entries; the one
match was the oldest, `### v0.1.0`, so every `CB` naming `v0.23.1` or later was denied. The
48 headings were renamed, and the version workflow in `CLAUDE.md` names the new form.

**The alternative rejected:** widening `ENTRY_LINE` in `hook_gate.py` — the kit's file
becomes customised and every future upgrade has to merge it. Also rejected: an `## Open:`
line — commits before `Let's finish` would carry an unreleased number, which changes the
version workflow rather than the heading.

**Instruments:** the gate fed a `git commit` command as a hook payload — `v0.23.1` allowed,
`v0.9.9` denied; check-links found no anchor that depended on the old form.

**Reverse:** `sed -i 's/^### v/### Changelog v/'` over the entries, and widen `ENTRY_LINE`.

