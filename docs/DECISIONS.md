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
